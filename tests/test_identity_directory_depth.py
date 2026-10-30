from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tests/check_identity_directory_lab.ps1"
SHELLS = [path for name in ("powershell.exe", "pwsh") if (path := shutil.which(name))]


@unittest.skipUnless(SHELLS, "PowerShell is required for domain-fixture plan boundary tests")
class DirectoryLabBoundaryTests(unittest.TestCase):
    """No domain connection or AD mutation occurs in these tests."""

    def plan(self, folder):
        return {
            "schema_version": "1.0", "lab_id": "directory-lab-unit-fixture01",
            "domain_dns": "directory-lab.test",
            "domain_guid": "11111111-1111-4111-8111-111111111111",
            "servers": [
                {"host": "dc1.directory-lab.test", "ntds_guid": "22222222-2222-4222-8222-222222222222"},
                {"host": "dc2.directory-lab.test", "ntds_guid": "33333333-3333-4333-8333-333333333333"},
            ],
            "ou_guid": "44444444-4444-4444-8444-444444444444",
            "object_guid": "55555555-5555-4555-8555-555555555555",
            "gpo_guid": "66666666-6666-4666-8666-666666666666",
            "backup_parent": str(folder),
            "script_sha256": hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
            "timeout_seconds": 30,
        }

    def invoke(self, shell, plan, folder, *arguments):
        path = folder / "plan.json"
        path.write_text(json.dumps(plan), encoding="utf-8")
        environment = dict(os.environ, PYTHONUTF8="1")
        if Path(shell).name.lower() == "powershell.exe":
            environment["PSModulePath"] = str(Path(environment["WINDIR"]) / "System32/WindowsPowerShell/v1.0/Modules")
        run = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-File", str(SCRIPT), "-PlanPath", str(path), *arguments], env=environment, capture_output=True, text=True, timeout=30)
        try:
            payload = json.loads(run.stdout)
        except ValueError:
            self.fail(run.stdout + run.stderr)
        self.assertNotEqual(payload["status"], "verified")
        return run, payload

    def test_default_is_offline_and_leaves_unrun_checks_explicit(self):
        for shell in SHELLS:
            with self.subTest(shell=shell), tempfile.TemporaryDirectory() as directory:
                folder = Path(directory)
                run, payload = self.invoke(shell, self.plan(folder), folder)
                self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
                self.assertEqual(payload["execution"], "plan_validated_only")
                for key in ("object_recovery", "gpo_recovery", "replication", "effective_policy", "delegated_identity_allow_deny", "sysvol_fault_recovery"):
                    self.assertEqual(payload[key], "not_run")
                self.assertEqual({path.name for path in folder.iterdir()}, {"plan.json"})

    def test_rejects_ambiguous_scope_default_policy_and_modified_code(self):
        cases = [
            lambda p: p.update(domain_dns="production.example.com"),
            lambda p: p.update(domain_guid="*"),
            lambda p: p.update(object_guid="00000000-0000-0000-0000-000000000000"),
            lambda p: p["servers"].pop(),
            lambda p: p["servers"][1].update(host=p["servers"][0]["host"]),
            lambda p: p["servers"][1].update(ntds_guid=p["servers"][0]["ntds_guid"]),
            lambda p: p["servers"][1].update(host="dc2.other.test"),
            lambda p: p.update(gpo_guid="31b2f340-016d-11d2-945f-00c04fb984f9"),
            lambda p: p.update(script_sha256="a" * 64),
            lambda p: p.update(timeout_seconds=True),
            lambda p: p.update(timeout_seconds=901),
            lambda p: p.update(approval=True),
        ]
        for shell in SHELLS:
            for index, change in enumerate(cases):
                with self.subTest(shell=shell, case=index), tempfile.TemporaryDirectory() as directory:
                    folder = Path(directory)
                    plan = self.plan(folder)
                    change(plan)
                    run, payload = self.invoke(shell, plan, folder)
                    self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
                    self.assertEqual(payload["execution"], "refused_or_incomplete")

    def test_execute_is_unconditionally_refused_before_native_calls(self):
        for shell in SHELLS:
            for forged in (False, True):
                with self.subTest(shell=shell, forged=forged), tempfile.TemporaryDirectory() as directory:
                    folder = Path(directory)
                    plan = self.plan(folder)
                    if forged:
                        plan.update(approval=True, owner_run=True, signed_grant="caller-assertion")
                    plan_path = folder / "plan.json"
                    plan_path.write_text(json.dumps(plan), encoding="utf-8")
                    trace_path = folder / "trace.txt"
                    environment = dict(os.environ)
                    if Path(shell).name.lower() == "powershell.exe":
                        environment["PSModulePath"] = str(Path(environment["WINDIR"]) / "System32/WindowsPowerShell/v1.0/Modules")
                    run = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-File", str(ROOT / "tests/check_directory_lab_mocks.ps1"), "-PlanPath", str(plan_path), "-TracePath", str(trace_path)], env=environment, capture_output=True, text=True, timeout=30)
                    self.assertEqual(run.returncode, 2, run.stdout + run.stderr)
                    payload = json.loads(run.stdout)
                    self.assertIn("registered immutable broker task", payload["error"])
                    self.assertFalse(trace_path.exists(), "Refused execution reached native tooling")
                    self.assertEqual(payload["object_recovery"], "not_run")
                    self.assertEqual(payload["gpo_recovery"], "not_run")
                    self.assertEqual({path.name for path in folder.iterdir()}, {"plan.json"})

    def test_readonly_requires_known_integer_versions_before_comparing(self):
        cases = [("valid", -1), ("valid-zero", -1), ("valid-mixed", -1), ("null", -1)]
        cases += [("null", field) for field in range(4)]
        cases += [(kind, -1) for kind in ("bool", "string", "negative", "nan", "infinite", "decimal", "local-mismatch", "dc-mismatch", "stale")]
        for shell in SHELLS:
            for scenario, field in cases:
                with self.subTest(shell=shell, scenario=scenario, field=field), tempfile.TemporaryDirectory() as directory:
                    folder = Path(directory)
                    plan_path = folder / "plan.json"
                    plan_path.write_text(json.dumps(self.plan(folder)), encoding="utf-8")
                    trace_path = folder / "mutation.txt"
                    environment = dict(os.environ)
                    if Path(shell).name.lower() == "powershell.exe":
                        environment["PSModulePath"] = str(Path(environment["WINDIR"]) / "System32/WindowsPowerShell/v1.0/Modules")
                    run = subprocess.run([shell, "-NoProfile", "-NonInteractive", "-File", str(ROOT / "tests/check_directory_lab_readonly_mocks.ps1"), "-PlanPath", str(plan_path), "-MutationTrace", str(trace_path), "-Scenario", scenario, "-CounterField", str(field)], env=environment, capture_output=True, text=True, timeout=30)
                    valid = scenario in {"valid", "valid-zero", "valid-mixed"}
                    self.assertEqual(run.returncode, 0 if valid else 2, run.stdout + run.stderr)
                    payload = json.loads(run.stdout)
                    self.assertEqual(payload["execution"], "readonly_preflight_completed" if valid else "refused_or_incomplete")
                    self.assertEqual(payload["status"], "partially_verified")
                    if not valid:
                        expected = {"local-mismatch": "Local GPC/GPT versions differ", "dc-mismatch": "GPO versions differ across DCs", "stale": "Replication baseline is not healthy"}.get(scenario, "observed nonnegative integer")
                        self.assertIn(expected, payload["error"])
                        self.assertEqual(payload["replication"], "not_run")
                    for key in ("object_recovery", "gpo_recovery", "effective_policy", "delegated_identity_allow_deny", "sysvol_fault_recovery"):
                        self.assertEqual(payload[key], "not_run")
                    self.assertFalse(trace_path.exists(), "Read-only preflight reached a mutation")
                    self.assertEqual({path.name for path in folder.iterdir()}, {"plan.json"})


if __name__ == "__main__":
    unittest.main()
