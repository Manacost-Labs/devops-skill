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
    def test_upgrade_refuses_a_busy_runtime_and_preserves_existing_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            runtime, ready, release = root/"runtime", root/"ready", root/"release"
            install = [PYTHON, str(ROOT/"tools/install.py"), "--runtime", "--destination", str(runtime), "--apply"]
            result = subprocess.run(install, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            journal = runtime/"operations/execution-ledger.jsonl"
            journal.parent.mkdir(exist_ok=True)
            journal.write_text('{"status":"historical-evidence"}\n', encoding="utf-8")
            before = journal.read_bytes()
            code = ("import importlib.util,time\nfrom pathlib import Path\n"
                    f"s=importlib.util.spec_from_file_location('holder',{str(runtime/'tools/runtime_lock.py')!r})\n"
                    "m=importlib.util.module_from_spec(s);s.loader.exec_module(m)\n"
                    f"with m.runtime_lock({str(runtime)!r}):\n Path({str(ready)!r}).touch()\n"
                    f" while not Path({str(release)!r}).exists(): time.sleep(.02)\n")
            running = subprocess.Popen([PYTHON, "-c", code], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                wait_for(ready,running)
                result = subprocess.run([*install,"--force"], capture_output=True,text=True)
                self.assertNotEqual(result.returncode,0)
                self.assertIn("busy",result.stdout)
                planner = subprocess.run([PYTHON,str(runtime/"tools/devops_plan.py"),"--help"], capture_output=True,text=True)
                self.assertNotEqual(planner.returncode,0)
                self.assertIn("busy",planner.stdout)
            finally:
                release.touch(); stdout,stderr=running.communicate(timeout=10)
            self.assertEqual(running.returncode,0,stdout+stderr)
            result = subprocess.run([*install,"--force"],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(journal.read_bytes(),before)

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




if __name__ == "__main__":
    unittest.main()
