"""Coordinate runtime writers across processes; sync POSIX journal directory entries."""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import os
from pathlib import Path
import stat


class RuntimeLockError(OSError):
    """The runtime could not be reserved; no protected operation may start."""


@contextmanager
def runtime_lock(runtime):
    # The lock must not move when an upgrade replaces the runtime directory.
    runtime = Path(runtime).resolve()
    key = hashlib.sha256(os.path.normcase(str(runtime)).encode("utf-8")).hexdigest()
    directory = runtime.parent / ".devops-skill-locks"
    descriptor = None
    try:
        directory.mkdir(parents=True, exist_ok=True)
        metadata = directory.lstat()
        reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        if stat.S_ISLNK(metadata.st_mode) or getattr(metadata, "st_file_attributes", 0) & reparse:
            raise OSError("lock directory must not be a symlink or reparse point")
        path = directory / (key + ".lock")
        if path.is_symlink() or (path.exists() and getattr(path.lstat(), "st_file_attributes", 0) & reparse):
            raise OSError("lock file must not be a symlink or reparse point")
        descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_BINARY", 0), 0o600)
        os.set_inheritable(descriptor, False)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise OSError("runtime lock must be a regular file")
        if os.name == "nt":
            import msvcrt
            # Windows supports locking a range beyond EOF; no pre-lock write is needed.
            os.lseek(descriptor, 0, os.SEEK_SET)
            msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as error:
        if descriptor is not None:
            os.close(descriptor)
        raise RuntimeLockError("runtime is busy or its coordination lock is unavailable") from error
    try:
        yield
    finally:
        # Native locks are also released by the OS if the owning process exits.
        os.close(descriptor)


def sync_directory(directory):
    if os.name != "posix":
        return
    descriptor = os.open(directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
