from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent


@unittest.skipUnless(os.name == "nt", "Windows PowerShell/native security descriptors")
class WindowsEvidenceTests(unittest.TestCase):
    def run_checks(self, executable):
        with tempfile.TemporaryDirectory(prefix="windows-unit-", dir=WORK) as directory:
            self.assertTrue(Path(directory).resolve().is_relative_to(WORK.resolve()))
            environment = dict(os.environ)
            if Path(executable).name.lower() == "powershell.exe":
                # A parent PS7 process may export its incompatible module directory.
                environment["PSModulePath"] = str(Path(environment["WINDIR"])/"System32/WindowsPowerShell/v1.0/Modules")
            result = subprocess.run([executable, "-NoProfile", "-NonInteractive", "-File", str(ROOT/"tests/check_windows_evidence.ps1"), "-ScratchRoot", directory], env=environment, capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("OK: native descriptor", result.stdout)

    def test_native_windows_powershell_51_and_readonly_helpers(self):
        self.run_checks("powershell.exe")

    def test_powershell_7_and_readonly_helpers(self):
        executable = shutil.which("pwsh")
        if not executable: self.skipTest("PowerShell 7 unavailable")
        self.run_checks(executable)
