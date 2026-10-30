"""Source-only helpers for owned, capability-free, socket-only recovery drills."""
from __future__ import annotations

import io
import re
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

from container_fixture import DockerFixture, OWNER


def require_native_rejection(returncode, evidence, pattern):
    if returncode == 0 or re.search(pattern, evidence, re.IGNORECASE) is None:
        raise RuntimeError("expected artifact-specific native rejection was not demonstrated: "+evidence[-1500:])


def extract_regular_archive(content, target):
    if len(content) > 256*1024*1024:
        raise RuntimeError("fixture archive size exceeded")
    with tarfile.open(fileobj=io.BytesIO(content), mode="r:") as archive:
        members = archive.getmembers()
        if sum(member.size for member in members) > 256*1024*1024:
            raise RuntimeError("fixture artifact size exceeded")
        names = set()
        for member in members:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or ".." in path.parts or "\\" in member.name
                    or not (member.isdir() or member.isfile()) or str(path) in names):
                raise RuntimeError("nonregular, duplicate or escaping fixture archive entry")
            names.add(str(path))
        target.mkdir(mode=0o700)
        archive.extractall(target, filter="data")


class RecoveryFixture(DockerFixture):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.cleanup()

    def engine(self, image, user):
        if not re.fullmatch(r"[a-z0-9:./-]+@sha256:[a-f0-9]{64}", image):
            raise RuntimeError("digest-pinned engine required")
        self.docker("pull", image, timeout=240)
        declared = self.inspect("image", image).get("Config", {}).get("Volumes") or {}
        if not set(declared) <= {"/data", "/var/lib/postgresql", "/var/lib/postgresql/data"}:
            raise RuntimeError("unexpected image volume boundary")
        # Override image VOLUMEs so Docker cannot silently allocate anonymous volumes.
        overrides = [argument for path in sorted(declared)
                     for argument in ("--tmpfs", path+":rw,mode=700,size=1m")]
        identity = self.docker(
            "create", "--name", self.tag+"-"+str(len(self.containers)),
            "--label", OWNER+"="+self.tag, "--network", "none", "--user", user,
            "--workdir", "/fixture",
            "--read-only", "--tmpfs", "/fixture:rw,mode=1777,size=768m",
            "--memory", "1g", "--memory-swap", "1g", "--cpus", "2",
            "--pids-limit", "128", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
            *overrides, "--entrypoint", "/bin/sleep", image, "infinity").stdout.strip()
        if not re.fullmatch(r"[a-f0-9]{64}", identity):
            raise RuntimeError("full engine container identity required")
        self.containers.append(identity)
        actual = self.owned_container(identity)
        host = actual["HostConfig"]
        if (host["NetworkMode"] != "none" or host.get("PortBindings")
                or host.get("Binds") or not host["ReadonlyRootfs"]
                or host.get("CapAdd") or host.get("CapDrop") != ["ALL"]
                or any(mount.get("Type") != "tmpfs" for mount in actual.get("Mounts", []))):
            raise RuntimeError("engine fixture isolation differs")
        self.docker("start", identity)
        return identity

    def execute(self, identity, *argv, input=None, expected=0, timeout=90):
        self.owned_container(identity)
        return self.docker("exec", "-i", identity, *argv, input=input,
                           expected=expected, timeout=timeout)

    def write(self, identity, path, content):
        # Only fixture-owned constant paths and synthetic content enter this helper.
        if not re.fullmatch(r"/fixture/[a-zA-Z0-9_./-]+", path) or ".." in Path(path).parts:
            raise RuntimeError("bounded fixture path required")
        self.execute(identity, "sh", "-c", 'cat > "$1"', "fixture-write", path, input=content)

    def export(self, identity, path, name):
        self.owned_container(identity)
        target = self.folder/name
        if target.exists() or target.parent != self.folder or not re.fullmatch(r"[a-z0-9-]+", name):
            raise RuntimeError("fresh owned export path required")
        if not re.fullmatch(r"/fixture/[a-z0-9-]+", path):
            raise RuntimeError("bounded fixture export root required")
        # docker cp's archive endpoint does not expose these tmpfs mounts reliably.
        content = self.binary(identity, ["tar", "--create", "--file=-", "--directory="+path, "."])
        extract_regular_archive(content, target)
        self.check_files(target)
        return target

    def import_tree(self, identity, source, path):
        self.owned_container(identity)
        self.check_files(source)
        if not re.fullmatch(r"/fixture/[a-z0-9-]+", path):
            raise RuntimeError("fresh fixture import root required")
        archive = io.BytesIO()
        with tarfile.open(fileobj=archive, mode="w") as output:
            output.add(source, arcname=Path(path).name)
        # Extract as the unprivileged engine identity; no CHOWN capability is needed.
        self.binary(identity, ["tar", "--extract", "--file=-", "--directory=/fixture",
                               "--no-same-owner"], input=archive.getvalue())

    def binary(self, identity, arguments, *, input=None):
        self.owned_container(identity)
        self.check_daemon()
        result = subprocess.run(["docker", "--host", "unix:///var/run/docker.sock", "--config",
                                 str(self.folder/"docker-config"), "exec", "-i", identity, *arguments],
                                env=self.environment, input=input, capture_output=True, timeout=90)
        if result.returncode or len(result.stdout) > 256*1024*1024:
            raise RuntimeError("binary fixture transfer failed: "+result.stderr.decode("utf-8", errors="replace")[-1000:])
        return result.stdout

    def check_files(self, source):
        source = Path(source)
        if self.folder not in source.resolve(strict=True).parents:
            raise RuntimeError("copy escaped fixture storage")
        for path in [source, *source.rglob("*")]:
            if path.is_symlink() or not (path.is_dir() or path.is_file()):
                raise RuntimeError("nonregular recovery fixture artifact")
