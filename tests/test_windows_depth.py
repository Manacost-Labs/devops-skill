from __future__ import annotations

import os
import json
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

    def test_installed_windows_profile_and_blackbox_entrypoints(self):
        import sys
        with tempfile.TemporaryDirectory(prefix="windows-unit-", dir=WORK) as directory:
            folder = Path(directory)
            self.assertTrue(folder.resolve().is_relative_to(WORK.resolve()))
            installed = folder/"skills"
            result = subprocess.run([sys.executable, str(ROOT/"tools/install.py"), "--profile", "windows-server", "--destination", str(installed), "--apply"], capture_output=True, text=True, timeout=30)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            environment = dict(os.environ, PSModulePath=str(Path(os.environ["WINDIR"])/"System32/WindowsPowerShell/v1.0/Modules"))
            scripts = installed/"windows-server-operations/scripts"
            def invoke(name, *arguments):
                return subprocess.run(["powershell.exe", "-NoProfile", "-NonInteractive", "-File", str(scripts/name), *arguments], env=environment, capture_output=True, text=True, timeout=30)
            source = folder/"fixture.txt"; source.write_text("synthetic", encoding="utf-8")
            result = invoke("inspect-file-access.ps1", "-LiteralPath", str(source))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["effective_access"], "not_evaluated")
            xml = folder/"task.xml"
            xml.write_text('<Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task"><Actions><Exec><Command>confidential-marker</Command></Exec></Actions></Task>', encoding="utf-8")
            result = invoke("inspect-task-definition.ps1", "-LiteralPath", str(xml))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(json.loads(result.stdout)["execution_authorized"])
            self.assertNotIn("confidential-marker", result.stdout + result.stderr)
            xml.write_text('<!DOCTYPE Task [<!ENTITY x SYSTEM "file:///never-read">]><Task xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">&x;</Task>', encoding="utf-8")
            result = invoke("inspect-task-definition.ps1", "-LiteralPath", str(xml))
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "unknown")
            result = invoke("inspect-certificate.ps1", "-StoreLocation", "CurrentUser", "-Thumbprint", "0" * 40)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertEqual(json.loads(result.stdout)["status"], "unknown")
