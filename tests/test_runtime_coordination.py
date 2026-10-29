"""Regression checks for actual cross-process runtime writers and journal durability."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

from test_enforcement import NOW, bound_operation

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def wait_for(path, process):
    deadline = time.monotonic() + 10
    while not path.exists() and process.poll() is None and time.monotonic() < deadline:
        time.sleep(0.02)
    if not path.exists():
        raise AssertionError("fixture process did not reach its ready marker")


class RuntimeCoordinationTests(unittest.TestCase):
    def test_upgrade_refuses_a_live_executor_and_preserves_its_final_record(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime, ready, release = root / "runtime", root / "ready", root / "release"
            install = [PYTHON, str(ROOT / "tools/install.py"), "--runtime", "--destination", str(runtime), "--apply"]
            result = subprocess.run(install, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            child = (
                "from pathlib import Path\nimport time\n"
                f"Path({str(ready)!r}).touch()\n"
                "deadline=time.monotonic()+20\n"
                f"while not Path({str(release)!r}).exists() and time.monotonic()<deadline:\n"
                " time.sleep(0.02)\n"
            )
            command = [PYTHON, "-c", child]
            request = root / "request.json"
            request.write_text(json.dumps(bound_operation(command)), encoding="utf-8")
            running = subprocess.Popen([PYTHON, str(runtime / "tools/devops_exec.py"),
                "--operation", str(request), "--at", NOW, "--", *command],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                wait_for(ready, running)
                result = subprocess.run([*install, "--force"], capture_output=True, text=True)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertIn("busy", result.stdout)
                planner = subprocess.run([PYTHON, str(runtime / "tools/devops_plan.py"), "--help"], capture_output=True, text=True)
                self.assertNotEqual(planner.returncode, 0)
                self.assertIn("busy", planner.stdout)
            finally:
                release.touch()
                stdout, stderr = running.communicate(timeout=25)
            self.assertEqual(running.returncode, 0, stdout + stderr)
            journal = runtime / "operations/execution-ledger.jsonl"
            before = journal.read_bytes()
            self.assertEqual([json.loads(line)["status"] for line in before.splitlines()], ["launch_intent", "executed"])
            upgraded = subprocess.run([*install, "--force"], capture_output=True, text=True)
            self.assertEqual(upgraded.returncode, 0, upgraded.stdout + upgraded.stderr)
            self.assertEqual(journal.read_bytes(), before)

    def test_native_lock_is_released_when_its_process_dies(self):
        support_path = ROOT / "tools/runtime_lock.py"
        support = load(support_path, "coordination_parent")
        with tempfile.TemporaryDirectory() as directory:
            runtime, ready = Path(directory) / "runtime", Path(directory) / "ready"
            script = (
                "import importlib.util,time\nfrom pathlib import Path\n"
                f"s=importlib.util.spec_from_file_location('lock_child',{str(support_path)!r})\n"
                "m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
                f"with m.runtime_lock({str(runtime)!r}):\n"
                f" Path({str(ready)!r}).touch()\n time.sleep(30)\n"
            )
            holder = subprocess.Popen([PYTHON, "-c", script])
            try:
                wait_for(ready, holder)
                with self.assertRaises(support.RuntimeLockError):
                    with support.runtime_lock(runtime):
                        self.fail("another process owns the runtime")
            finally:
                holder.kill()
                holder.wait(timeout=5)
            with support.runtime_lock(runtime):
                self.assertFalse(os.path.exists(runtime))

    def test_journal_syncs_containing_and_new_parent_directory_entries(self):
        module = load(ROOT / "tools/devops_exec.py", "directory_sync_probe")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            journal = root / "new-parent/new-leaf/ledger.jsonl"
            observed = []
            def sync(path):
                self.assertTrue(journal.is_file())
                self.assertEqual(json.loads(journal.read_text(encoding="utf-8"))["status"], "launch_intent")
                observed.append(path)
                module._support.sync_directory(path)
            with mock.patch.object(module, "sync_directory", side_effect=sync):
                module.append_ledger(journal, {"status": "launch_intent"})
            self.assertEqual(set(observed), {root, root / "new-parent", journal.parent})

    def test_directory_sync_failure_prevents_process_creation(self):
        module = load(ROOT / "tools/devops_exec.py", "directory_sync_failure")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker, journal = root / "must-not-exist", root / "new/ledger.jsonl"
            command = [PYTHON, "-c", f"from pathlib import Path; Path({str(marker)!r}).touch()"]
            request = root / "request.json"
            request.write_text(json.dumps(bound_operation(command)), encoding="utf-8")
            argv = [str(ROOT / "tools/devops_exec.py"), "--operation", str(request),
                    "--at", NOW, "--ledger", str(journal), "--", *command]
            with mock.patch.object(module, "sync_directory", side_effect=OSError("injected directory sync failure")), mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()) as output:
                result = module.main()
            self.assertEqual(result, 3, output.getvalue())
            self.assertFalse(marker.exists())


if __name__ == "__main__":
    unittest.main()
