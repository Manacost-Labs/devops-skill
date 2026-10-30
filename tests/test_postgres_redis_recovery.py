"""Guard against false-positive native refusals and unsafe fixture artifact transfer."""
from __future__ import annotations

import io
import tarfile
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from recovery_fixture import extract_regular_archive, require_native_rejection
from smoke_postgres_recovery import UNREACHED, WRONG_WAL_SIZE, require_startup_failure


def tar_bytes(entries):
    content = io.BytesIO()
    with tarfile.open(fileobj=content, mode="w") as archive:
        for name, kind in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            if kind in (tarfile.SYMTYPE, tarfile.LNKTYPE):
                member.linkname = "../../outside"
            body = b"synthetic" if kind == tarfile.REGTYPE else b""
            member.size = len(body)
            archive.addfile(member, io.BytesIO(body))
    return content.getvalue()


class NativeRejectionEvidenceTests(unittest.TestCase):
    def test_generic_startup_or_checker_errors_are_not_recovery_evidence(self):
        for evidence in ("Permission denied", "FATAL: unrecognized configuration parameter",
                         "Cannot open file: Permission denied", "Killed by OOM"):
            for pattern in (UNREACHED, WRONG_WAL_SIZE, r"RDB CRC error", r"AOF [^\n]+ is not valid"):
                with self.subTest(evidence=evidence, pattern=pattern), self.assertRaises(RuntimeError):
                    require_native_rejection(1, evidence, pattern)

    def test_successful_process_with_error_text_is_not_a_rejection(self):
        with self.assertRaises(RuntimeError):
            require_native_rejection(0, "RDB CRC error", r"RDB CRC error")

    def test_rejection_requires_both_nonzero_exit_and_specific_evidence(self):
        require_native_rejection(1, "FATAL: recovery ended before configured recovery target was reached", UNREACHED)

    def test_short_archive_has_its_own_fatal_cause_before_target_evaluation(self):
        # PG18 aborts in archive-size verification before it can evaluate the target.
        expected = '2026-10-30 [123] FATAL:  archive file "000000010000000000000004" has wrong size: 18 instead of 1048576'
        for evidence, accepted in ((expected, True), ("FATAL: Permission denied", False),
                                   ("FATAL: unrecognized configuration parameter", False)):
            fixture = SimpleNamespace(execute=lambda _identity, *argv, **_kwargs: SimpleNamespace(
                returncode=3 if "status" in argv else 1, stdout=evidence if argv[0] == "cat" else ""))
            with self.subTest(evidence=evidence):
                if accepted:
                    require_startup_failure(fixture, "synthetic", "short WAL", expected_pattern=WRONG_WAL_SIZE)
                else:
                    with self.assertRaises(RuntimeError):
                        require_startup_failure(fixture, "synthetic", "short WAL", expected_pattern=WRONG_WAL_SIZE)


class RecoveryTransferBoundaryTests(unittest.TestCase):
    def test_regular_artifacts_extract_into_fresh_owned_directory(self):
        content = tar_bytes([("base", tarfile.DIRTYPE), ("base/PG_VERSION", tarfile.REGTYPE)])
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder)/"copy"
            extract_regular_archive(content, target)
            self.assertEqual((target/"base/PG_VERSION").read_bytes(), b"synthetic")

    def test_escaping_or_link_entries_rejected_before_any_extraction(self):
        entries = [("../../outside", tarfile.REGTYPE), ("/outside", tarfile.REGTYPE),
                   ("base\\outside", tarfile.REGTYPE), ("base/link", tarfile.SYMTYPE),
                   ("base/link", tarfile.LNKTYPE), ("base/fifo", tarfile.FIFOTYPE)]
        for entry in entries:
            with self.subTest(entry=entry), tempfile.TemporaryDirectory() as folder:
                target = Path(folder)/"copy"
                with self.assertRaises(RuntimeError):
                    extract_regular_archive(tar_bytes([("safe", tarfile.REGTYPE), entry]), target)
                self.assertFalse(target.exists())
                self.assertEqual(list(Path(folder).iterdir()), [])

    def test_duplicate_normalized_entries_rejected(self):
        content = tar_bytes([("base/file", tarfile.REGTYPE), ("./base/file", tarfile.REGTYPE)])
        with tempfile.TemporaryDirectory() as folder, self.assertRaises(RuntimeError):
            extract_regular_archive(content, Path(folder)/"copy")


if __name__ == "__main__":
    unittest.main()
