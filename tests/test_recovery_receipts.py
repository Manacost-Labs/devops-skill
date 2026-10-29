from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT/"data-resilience-operations/scripts/verify-binlog-chain.py"
spec = importlib.util.spec_from_file_location("verify_binlog_chain", SCRIPT)
CHECK = importlib.util.module_from_spec(spec)
spec.loader.exec_module(CHECK)


def fixture(root):
    backup = b"synthetic base artifact, not executable production SQL\n"
    logs = [b"\xfebin" + b"a" * 60, b"\xfebin" + b"b" * 60]
    def write(name, data):
        (root/name).write_bytes(data)
        return {"file": name, "size": len(data), "sha256": hashlib.sha256(data).hexdigest()}
    return {"schema_version": "1.0", "engine": "mysql", "source_ref": "inventory:synthetic", "coordinate_evidence_ref": "evidence:snapshot", "boundary_evidence_ref": "evidence:transaction-stop", "backup": write("base.sql", backup), "start": {"name": "binlog.000021", "position": 10}, "stop": {"name": "binlog.000022", "position": 40}, "logs": [{"name": f"binlog.{21+i:06d}", **write(f"binlog.{21+i:06d}", value)} for i, value in enumerate(logs)]}


class RecoveryReceiptTests(unittest.TestCase):
    @unittest.skipUnless(os.name == "posix", "POSIX FIFO race")
    def test_swapped_fifo_cannot_block_artifact_open(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); data = fixture(root)
            original_open = CHECK.os.open
            swapped = False
            def replace_before_open(path, flags, *args, **kwargs):
                nonlocal swapped
                if path == "base.sql" and not swapped:
                    swapped = True
                    (root/"base.sql").unlink()
                    os.mkfifo(root/"base.sql")
                return original_open(path, flags, *args, **kwargs)
            with mock.patch.object(CHECK.os, "open", side_effect=replace_before_open):
                with self.assertRaises(ValueError): CHECK.verify(data, root)
            self.assertTrue(swapped)

    def test_valid_artifact_bytes_do_not_claim_replay_proof(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); data = fixture(root)
            for engine in ("mysql", "mariadb"):
                data["engine"] = engine
                result = CHECK.verify(data, root)
                self.assertEqual(result["status"], "integrity_verified_replay_unproven")
                self.assertEqual(result["log_count"], 2)
                self.assertEqual(result["bytes_hashed"], data["backup"]["size"] + 128)

    def test_gaps_reordering_wrong_history_and_extra_logs_rejected(self):
        mutations = [lambda d: d["logs"].pop(0), lambda d: d["logs"].reverse(), lambda d: d["stop"].update(name="foreign.000022"), lambda d: d["logs"][1].update(name="binlog.000023"), lambda d: d["logs"].append(copy.deepcopy(d["logs"][-1]))]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); data = fixture(root); mutate(data)
                with self.assertRaises(ValueError): CHECK.verify(data, root)

    def test_same_file_intervals_and_bounds(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); data = fixture(root)
            data["logs"] = data["logs"][:1]; data["stop"]["name"] = "binlog.000021"
            data["stop"]["position"] = 64
            self.assertEqual(CHECK.verify(data, root)["log_count"], 1)
            for start, stop in ((10, 10), (20, 10), (3, 20), (10, 65), (64, 64)):
                data["start"]["position"], data["stop"]["position"] = start, stop
                with self.subTest(start=start, stop=stop), self.assertRaises(ValueError): CHECK.verify(data, root)

    def test_unicode_coordinate_digits_are_not_filename_aliases(self):
        for start, stop in (("binlog.００００２１", "binlog.００００２２"), ("binlog.٠٠٠٠٢١", "binlog.٠٠٠٠٢٢")):
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory); data = fixture(root)
                data["start"]["name"], data["stop"]["name"] = start, stop
                with self.assertRaises(ValueError): CHECK.verify(data, root)

    def test_corruption_truncation_magic_and_budget_fail_closed(self):
        for mode in ("corrupt", "truncate", "magic", "budget"):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); data = fixture(root)
                path = root/data["logs"][0]["file"]
                content = path.read_bytes()
                if mode == "corrupt": path.write_bytes(content[:-1] + b"z")
                if mode == "truncate": path.write_bytes(content[:-1])
                if mode == "magic":
                    changed = b"nope" + content[4:]; path.write_bytes(changed)
                    data["logs"][0]["sha256"] = hashlib.sha256(changed).hexdigest()
                with self.assertRaises(ValueError): CHECK.verify(data, root, 1 if mode == "budget" else 1 << 30)

    def test_portable_paths_cannot_escape_or_alias(self):
        for name in ("../base.sql", "/base.sql", "C:/base.sql", "dir\\base.sql", "./base.sql", "dir//base.sql", "base.sql:stream", "CON.sql", "base.sql."):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); data = fixture(root); data["backup"]["file"] = name
                with self.assertRaises((ValueError, OSError)): CHECK.verify(data, root)

    def test_symlink_and_hardlink_not_accepted_as_independent_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); data = fixture(root)
            source = root/"base.sql"; link = root/"alias.sql"
            try: os.link(source, link)
            except OSError: self.skipTest("hard links unavailable")
            with self.assertRaises(ValueError): CHECK.verify(data, root)
            link.unlink()
            try: link.symlink_to(source)
            except OSError: return  # Symlink privilege is optional on Windows.
            data["backup"]["file"] = "alias.sql"
            with self.assertRaises(ValueError): CHECK.verify(data, root)

    def test_malformed_metadata_is_not_coerced(self):
        mutations = [lambda d: d.update(approval=True), lambda d: d.update(engine="postgresql"), lambda d: d.update(source_ref="literal value with spaces"), lambda d: d["backup"].update(size=True), lambda d: d["backup"].update(size=-1), lambda d: d["backup"].update(sha256="x"*64), lambda d: d["start"].update(position=4.0), lambda d: d["logs"][0].update(file="BASE.SQL")]
        for mutate in mutations:
            with self.subTest(mutate=mutate), tempfile.TemporaryDirectory() as directory:
                root = Path(directory); data = fixture(root); mutate(data)
                with self.assertRaises((ValueError, OSError)): CHECK.verify(data, root)

    def test_cli_never_echoes_untrusted_receipt_or_error_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); data = fixture(root); receipt = root/"receipt.json"
            receipt.write_text(json.dumps(data), encoding="utf-8")
            result = subprocess.run([sys.executable, str(SCRIPT), str(receipt), "--root", str(root)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            for content in ('{"confidential-marker":1,"confidential-marker":2}', '[', '[]', '{"x":NaN}', '[' * 1500):
                receipt.write_text(content, encoding="utf-8")
                result = subprocess.run([sys.executable, str(SCRIPT), str(receipt), "--root", str(root)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertNotIn("confidential-marker", result.stdout + result.stderr)
                self.assertNotIn(str(root), result.stdout + result.stderr)

    def test_installed_recovery_helper_is_self_contained(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); artifacts = root/"artifacts"; artifacts.mkdir()
            data = fixture(artifacts); receipt = root/"receipt.json"; receipt.write_text(json.dumps(data), encoding="utf-8")
            destination = root/"skills"
            installed = subprocess.run([sys.executable, str(ROOT/"tools/install.py"), "--profile", "data-safe", "--destination", str(destination), "--apply"], capture_output=True, text=True)
            self.assertEqual(installed.returncode, 0, installed.stdout + installed.stderr)
            helper = destination/"data-resilience-operations/scripts/verify-binlog-chain.py"
            checked = subprocess.run([sys.executable, str(helper), str(receipt), "--root", str(artifacts)], capture_output=True, text=True)
            self.assertEqual(checked.returncode, 0, checked.stderr)
            self.assertEqual(json.loads(checked.stdout)["log_count"], 2)
