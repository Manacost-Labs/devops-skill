from __future__ import annotations

import copy
import importlib.util
import json
import os
import random
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


BUDGET = load("connection_budget", "database-operations/scripts/connection-budget.py")
SLO = load("slo_evaluate", "reliability-operations/scripts/slo-evaluate.py")


def budget():
    return {"engine_max": 200, "reserved": 15, "other_peak": 10,
            "pools": [{"name": "api", "instances": 6, "per_instance": 20},
                      {"name": "jobs", "instances": 2, "per_instance": 10}]}


def slo():
    return {"objective": Decimal("0.999"), "windows": [
        {"name": "long", "seconds": 3600, "total": 100000, "bad": 2000},
        {"name": "short", "seconds": 300, "total": 10000, "bad": 200}],
        "alert": {"long": "long", "short": "short", "threshold": Decimal("14.4"), "minimum_events": 100}}


class BudgetTests(unittest.TestCase):
    def test_backend_budget_and_boundary(self):
        data = budget()
        self.assertEqual(BUDGET.evaluate(data), {"pools": [{"name": "api", "backend_peak": 120}, {"name": "jobs", "backend_peak": 20}], "application_peak": 140, "usable_slots": 185, "backend_peak": 150, "committed_slots": 165, "headroom": 35, "status": "fits"})
        for maximum, status, headroom in [(165, "at_limit", 0), (164, "exceeds", -1)]:
            data["engine_max"] = maximum
            self.assertEqual((BUDGET.evaluate(data)["status"], BUDGET.evaluate(data)["headroom"]), (status, headroom))

    def test_autoscale_demand_is_monotonic(self):
        rng = random.Random(73)
        for _ in range(50):
            data = budget()
            data["pools"][0]["instances"] = rng.randint(1, 100)
            before = BUDGET.evaluate(data)
            data["pools"][0]["instances"] += 1
            after = BUDGET.evaluate(data)
            self.assertEqual(before["headroom"] - after["headroom"], 20)

    def test_invalid_and_ambiguous_counts(self):
        for bad in (True, False, 1.5, "20", -1, None, 10**20):
            data = budget(); data["other_peak"] = bad
            with self.subTest(bad=bad), self.assertRaises(ValueError): BUDGET.evaluate(data)
        for key in ("engine_max", "reserved", "other_peak", "pools"):
            data = budget(); del data[key]
            with self.assertRaises(ValueError): BUDGET.evaluate(data)
        for mutate in (lambda d: d.update(password="opaque-fixture"), lambda d: d.update(reserved=200), lambda d: d["pools"].append(copy.deepcopy(d["pools"][0])), lambda d: d["pools"][0].update(instances=0)):
            data = budget(); mutate(data)
            with self.assertRaises(ValueError): BUDGET.evaluate(data)


class SloTests(unittest.TestCase):
    def test_known_burn_and_paired_threshold(self):
        data = slo()
        result = SLO.evaluate(data)
        self.assertEqual(Decimal(result["windows"]["long"]["burn_rate"]), 20)
        self.assertEqual(result["pair_status"], "firing")
        data["windows"][1]["bad"] = 0
        self.assertEqual(SLO.evaluate(data)["pair_status"], "clear")
        data["windows"][1]["bad"] = 144
        self.assertEqual(SLO.evaluate(data)["pair_status"], "firing")
        data["windows"][1]["bad"] = 143
        self.assertEqual(SLO.evaluate(data)["pair_status"], "clear")

    def test_no_or_low_traffic_is_insufficient(self):
        for total in (0, 99):
            data = slo(); data["windows"][1].update(total=total, bad=0)
            result = SLO.evaluate(data)
            self.assertEqual(result["pair_status"], "insufficient_data")
            if total == 0: self.assertIsNone(result["windows"]["short"]["burn_rate"])

    def test_rejects_invalid_numbers_counts_and_pair(self):
        for total, bad in ((10000, 3000), (100001, 0)):
            data = slo(); data["windows"][1].update(total=total, bad=bad)
            with self.assertRaises(ValueError): SLO.evaluate(data)
        for value in (True, 0, 1, -1, float("nan"), float("inf"), "0.999"):
            data = slo(); data["objective"] = value
            with self.subTest(value=value), self.assertRaises(ValueError): SLO.evaluate(data)
        for mutate in (lambda d: d["windows"][0].update(bad=100001), lambda d: d["windows"][0].update(total=True), lambda d: d["windows"].append(copy.deepcopy(d["windows"][0])), lambda d: d["alert"].update(short="missing"), lambda d: d["alert"].update(short="long"), lambda d: d["alert"].update(minimum_events=0), lambda d: d["alert"].update(threshold=Decimal("NaN")), lambda d: d.update(extra=1)):
            data = slo(); mutate(data)
            with self.assertRaises(ValueError): SLO.evaluate(data)


class HelperCliTests(unittest.TestCase):
    def test_data_safe_install_keeps_database_resources_self_contained(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory)/"skills"
            result = subprocess.run([sys.executable, str(ROOT/"tools/install.py"), "--profile", "data-safe", "--destination", str(destination), "--apply"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            for engine in ("postgresql", "mysql", "mariadb"):
                self.assertTrue((destination/f"database-operations/scripts/{engine}-diagnostics.sql").is_file())
            payload = Path(directory)/"budget.json"
            payload.write_text(json.dumps(budget()), encoding="utf-8")
            result = subprocess.run([sys.executable, str(destination/"database-operations/scripts/connection-budget.py"), str(payload)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["headroom"], 35)
            result = subprocess.run([sys.executable, str(destination/"devops-platform-contracts/scripts/validate_platform.py")], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_cli_rejects_duplicate_keys_without_echoing_input(self):
        for script, valid in [(BUDGET.__file__, budget()), (SLO.__file__, slo())]:
            with tempfile.TemporaryDirectory() as directory:
                path = Path(directory)/"input.json"
                path.write_text(json.dumps(valid, default=float), encoding="utf-8")
                result = subprocess.run([sys.executable, script, str(path)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                json.loads(result.stdout)
                for payload in ('{"sensitive_marker":1,"sensitive_marker":2}', '[]', '{"x":NaN}', '[' * 1500):
                    path.write_text(payload, encoding="utf-8")
                    result = subprocess.run([sys.executable, script, str(path)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 2, result.stderr)
                    self.assertNotIn("sensitive_marker", result.stdout + result.stderr)


@unittest.skipUnless(sys.platform.startswith("linux"), "actual Linux host discovery")
class HostAuditTests(unittest.TestCase):
    def test_probe_output_is_bounded_even_for_one_very_long_line(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory)/"ss"
            fake.write_text("#!/bin/sh\nhead -c 200000 /dev/zero | tr '\\000' X\n", encoding="utf-8")
            fake.chmod(0o755)
            env = dict(os.environ, PATH=directory + os.pathsep + os.environ["PATH"])
            result = subprocess.run(["bash", str(ROOT/"linux-operations/scripts/host-audit")], env=env, capture_output=True, text=True, timeout=80)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertLessEqual(result.stdout.count("X"), 16384)
            self.assertIn("at most 16 KiB", result.stdout)

    def test_os_release_is_untrusted_data_not_shell_code(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            marker = folder/"executed"
            release = folder/"os-release"
            release.write_text(f'ID=rocky\nVERSION_ID="9"\nPRETTY_NAME="$(touch {marker})"\n', encoding="utf-8")
            # Relocate the fixed input path to an attacker-controlled fixture only.
            source = (ROOT/"linux-operations/scripts/host-audit").read_text(encoding="utf-8")
            script = folder/"host-audit"
            script.write_text(source.replace("/etc/os-release", str(release)), encoding="utf-8")
            result = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=80)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse(marker.exists())
            self.assertIn("$(touch", result.stdout)

    def test_host_audit_reports_visibility_without_repair(self):
        script = ROOT/"linux-operations/scripts/host-audit"
        subprocess.run(["bash", "-n", str(script)], check=True)
        result = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=80)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("discovery only", result.stdout)
        self.assertIn("not collected; no package manager", result.stdout)
        self.assertIn("unavailable_checks", result.stdout)

    def test_missing_timeout_does_not_run_unbounded_probe(self):
        with tempfile.TemporaryDirectory() as directory:
            # Only required core tools are present; optional probes must be skipped.
            for command in ("date", "uname", "awk", "cat"):
                target = subprocess.run(["which", command], capture_output=True, text=True, check=True).stdout.strip()
                (Path(directory)/command).symlink_to(target)
            env = dict(os.environ, PATH=directory)
            result = subprocess.run(["/bin/bash", str(ROOT/"linux-operations/scripts/host-audit")], env=env, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("unknown/unavailable", result.stdout)
            self.assertNotIn("no immediate warning", result.stdout)
