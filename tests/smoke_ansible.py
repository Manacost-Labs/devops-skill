#!/usr/bin/env python3
"""Real Ansible orchestration on three local synthetic hosts; no live targets.

Run explicitly in its pinned Linux CI job. Missing Ansible/platform is an error,
never a skipped native test. Files represent config/active/traffic state only;
this does not exercise SSH, real services, cloud APIs, quorum or data recovery.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests/fixtures/ansible"
HOSTS = ("node1", "node2", "node3")


class NativeAnsibleTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue(sys.platform.startswith("linux"), "native Ansible job requires Linux")
        self.assertIsNotNone(shutil.which("ansible-playbook"), "install pinned native CI requirements")
        self.temp = tempfile.TemporaryDirectory(prefix="devops-ansible-")
        self.addCleanup(self.temp.cleanup)
        self.lab = Path(self.temp.name).resolve()
        self.lab.chmod(0o700)
        (self.lab / "validate.py").write_text(
            "import pathlib, sys\n"
            "content = pathlib.Path(sys.argv[1]).read_text()\n"
            "sys.exit(0 if content in ('release=v1\\n', 'release=v2\\n') else 1)\n", encoding="utf-8")
        (self.lab / "activate.py").write_text(
            "import pathlib, sys\n"
            "root = pathlib.Path(sys.argv[1])\n"
            "(root / 'active').write_bytes((root / 'config').read_bytes())\n"
            "counter = root / 'activations'\n"
            "counter.write_text(str(int(counter.read_text()) + 1))\n", encoding="utf-8")
        variables = {}
        for host in HOSTS:
            folder = self.lab / host
            folder.mkdir(mode=0o700)
            for name, content in {"config": "release=v1\n", "active": "release=v1\n", "traffic": "ready\n", "activations": "0"}.items():
                (folder / name).write_text(content, encoding="utf-8")
                (folder / name).chmod(0o600)
            variables[host] = {"host_root": str(folder)}
        self.inventory = {"all": {"vars": {
            "ansible_connection": "local", "ansible_python_interpreter": sys.executable,
            "ansible_become": False, "lab_root": str(self.lab),
            "release": "v2", "fail_host": "", "disconnect_host": "", "recovery_fails": False, "halt_after_rescue": True,
        }, "children": {
            "app": {"hosts": variables},
            "production": {"hosts": {"node1": {}, "node2": {}}},
            "maintenance": {"hosts": {"node2": {}}},
        }}}
        self.inventory_path = self.lab / "inventory.json"
        # A fresh controller configuration avoids inherited credentials, plugins,
        # fact caches, repository ansible.cfg or user inventory.
        self.config = self.lab / "ansible.cfg"
        self.config.write_text("[defaults]\nretry_files_enabled=False\nhost_key_checking=True\n", encoding="utf-8")
        self.env = {key: value for key, value in os.environ.items() if not key.startswith("ANSIBLE_")}
        self.env.update({
            "ANSIBLE_CONFIG": str(self.config), "ANSIBLE_NOCOLOR": "1",
            "ANSIBLE_LOCAL_TEMP": str(self.lab / "controller-tmp"),
            "ANSIBLE_REMOTE_TEMP": str(self.lab / "remote-tmp"),
            "ANSIBLE_CALLBACK_PLUGINS": str(FIXTURES / "callback_plugins"),
            "ANSIBLE_CALLBACKS_ENABLED": "fixture_evidence",
            "ANSIBLE_CONNECTION_PLUGINS": str(FIXTURES / "connection_plugins"),
            "ANSIBLE_LAB_DISCONNECT": str(self.lab / "node2/connection-lost"),
        })
        self.sequence = 0

    def read(self, host, filename):
        return (self.lab / host / filename).read_text(encoding="utf-8")

    def run_play(self, name, *, limit="app", variables=None, extra=(), expected=0):
        self.inventory_path.write_text(json.dumps(self.inventory), encoding="utf-8")
        self.inventory_path.chmod(0o600)
        self.sequence += 1
        evidence = self.lab / f"evidence-{self.sequence}.jsonl"
        env = dict(self.env, ANSIBLE_LAB_EVIDENCE=str(evidence))
        argv = ["ansible-playbook", "-i", str(self.inventory_path), str(FIXTURES / name), "--limit", limit, *extra]
        if variables:
            inputs = self.lab / f"vars-{self.sequence}.json"
            inputs.write_text(json.dumps(variables), encoding="utf-8")
            argv.extend(["--extra-vars", "@" + str(inputs)])
        result = subprocess.run(argv, cwd=self.lab, env=env, capture_output=True, text=True, timeout=150)
        detail = result.stdout[-14000:] + result.stderr[-4000:]
        if expected == 0:
            self.assertEqual(result.returncode, 0, detail)
        else:
            self.assertNotEqual(result.returncode, 0, detail)
        self.assertTrue(evidence.is_file(), "real callback evidence missing\n" + detail)
        events = [json.loads(line) for line in evidence.read_text(encoding="utf-8").splitlines()]
        stats = [event["hosts"] for event in events if event["event"] == "stats"]
        self.assertEqual(len(stats), 1, detail)
        return stats[0], events

    def test_second_convergence_has_no_changes_or_extra_handler(self):
        first, _ = self.run_play("converge.yml")
        self.assertEqual(set(first), set(HOSTS))
        for host in HOSTS:
            self.assertGreater(first[host]["changed"], 0)
            self.assertEqual(self.read(host, "active"), "release=v2\n")
            # Two notifications produce one actual activation per host.
            self.assertEqual(self.read(host, "activations"), "1")
        before = {(host, file): (self.lab / host / file).stat().st_mtime_ns for host in HOSTS for file in ("config", "active", "settings", "activations")}
        second, _ = self.run_play("converge.yml")
        self.assertEqual(set(second), set(HOSTS))
        for host in HOSTS:
            self.assertEqual(second[host]["changed"], 0)
            self.assertEqual(self.read(host, "activations"), "1")
        self.assertEqual(before, {(host, file): (self.lab / host / file).stat().st_mtime_ns for host, file in before})

    def test_canary_repeatability_precedes_any_fleet_expansion(self):
        self.run_play("converge.yml", limit="node1")
        repeated, _ = self.run_play("converge.yml", limit="node1")
        self.assertEqual(set(repeated), {"node1"})
        self.assertEqual(repeated["node1"]["changed"], 0)
        self.assertEqual(self.read("node1", "activations"), "1")
        for host in ("node2", "node3"):
            self.assertEqual(self.read(host, "config"), "release=v1\n")
            self.assertEqual(self.read(host, "activations"), "0")
        expanded, _ = self.run_play("converge.yml", limit="node2,node3")
        self.assertEqual(set(expanded), {"node2", "node3"})
        self.assertTrue(all(self.read(host, "active") == "release=v2\n" for host in HOSTS))

    def test_check_mode_does_not_write_fixture_and_validated_copy_rejects_bad_config(self):
        self.run_play("converge.yml")
        self.run_play("converge.yml", variables={"release": "v1"}, extra=("--check", "--diff"))
        self.assertTrue(all(self.read(host, "config") == "release=v2\n" for host in HOSTS))
        stats, _ = self.run_play("converge.yml", limit="node1", variables={"release": "invalid"}, expected=1)
        self.assertGreater(stats["node1"]["failures"], 0)
        self.assertEqual(self.read("node1", "config"), "release=v2\n")
        self.assertEqual(self.read("node1", "active"), "release=v2\n")
        self.assertEqual(self.read("node1", "activations"), "1")

    def test_only_drifted_host_changes_and_reactivates(self):
        self.run_play("converge.yml")
        (self.lab / "node2/config").write_text("release=v1\n", encoding="utf-8")
        stats, _ = self.run_play("converge.yml")
        self.assertEqual([host for host in HOSTS if stats[host]["changed"]], ["node2"])
        self.assertEqual([self.read(host, "activations") for host in HOSTS], ["1", "2", "1"])

    def test_group_intersection_exclusion_and_union_are_different(self):
        selected, _ = self.run_play("converge.yml", limit="app:&production:!maintenance")
        self.assertEqual(set(selected), {"node1"})
        self.assertEqual(self.read("node2", "config"), "release=v1\n")
        self.assertEqual(self.read("node3", "config"), "release=v1\n")
        union, _ = self.run_play("converge.yml", limit="app:production")
        self.assertEqual(set(union), set(HOSTS))

    def test_partial_failure_restores_file_halts_next_batch_then_targeted_resume(self):
        stats, _ = self.run_play("rolling.yml", variables={"fail_host": "node2"}, expected=1)
        self.assertEqual(self.read("node1", "active"), "release=v2\n")
        self.assertEqual(self.read("node1", "traffic"), "ready\n")
        self.assertEqual(self.read("node2", "config"), "release=v1\n")
        self.assertEqual(self.read("node2", "active"), "release=v1\n")
        self.assertEqual(self.read("node2", "traffic"), "excluded\n")
        self.assertGreater(stats["node2"]["rescued"], 0)
        self.assertGreater(stats["node2"]["failures"], 0)
        self.assertNotIn("node3", stats)
        self.assertEqual(self.read("node3", "config"), "release=v1\n")
        self.assertFalse((self.lab / "node3/observed").exists())
        resumed, _ = self.run_play("rolling.yml", limit="node2,node3")
        self.assertEqual(set(resumed), {"node2", "node3"})
        for host in HOSTS:
            self.assertEqual(self.read(host, "active"), "release=v2\n")
            self.assertEqual(self.read(host, "traffic"), "ready\n")
            self.assertEqual(self.read(host, "activations"), "1")
        repeated, _ = self.run_play("rolling.yml")
        self.assertTrue(all(value["changed"] == 0 for value in repeated.values()))

    def test_successful_rescue_alone_allows_next_batch_despite_failed_update(self):
        stats, _ = self.run_play("rolling.yml", variables={"fail_host": "node2", "halt_after_rescue": False})
        self.assertGreater(stats["node2"]["rescued"], 0)
        self.assertEqual(stats["node2"]["failures"], 0)
        self.assertEqual(self.read("node2", "traffic"), "excluded\n")
        self.assertEqual(self.read("node3", "active"), "release=v2\n")

    def test_failed_recovery_keeps_mixed_state_visible_and_later_node_untouched(self):
        stats, _ = self.run_play("rolling.yml", variables={"fail_host": "node2", "recovery_fails": True}, expected=1)
        self.assertGreater(stats["node2"]["failures"], 0)
        self.assertEqual(self.read("node2", "config"), "release=v2\n")
        self.assertEqual(self.read("node2", "active"), "release=v1\n")
        self.assertEqual(self.read("node2", "traffic"), "excluded\n")
        self.assertEqual(self.read("node3", "config"), "release=v1\n")
        self.assertNotIn("node3", stats)

    def test_connection_loss_after_config_change_does_not_enter_rescue_or_complete_always(self):
        self.inventory["all"]["children"]["app"]["hosts"]["node2"]["ansible_connection"] = "fixture_unreachable"
        stats, events = self.run_play("rolling.yml", variables={"disconnect_host": "node2"}, expected=1)
        self.assertGreaterEqual(stats["node2"]["unreachable"], 1)
        self.assertEqual(stats["node2"]["rescued"], 0)
        self.assertIn({"event": "unreachable", "host": "node2"}, events)
        self.assertEqual(self.read("node2", "config"), "release=v2\n")
        self.assertEqual(self.read("node2", "active"), "release=v1\n")
        self.assertEqual(self.read("node2", "traffic"), "excluded\n")
        self.assertFalse((self.lab / "node2/observed").exists())
        self.assertNotIn("node3", stats)
        self.assertEqual(self.read("node3", "config"), "release=v1\n")

    def test_initial_connection_loss_is_unknown_not_success(self):
        self.inventory["all"]["children"]["app"]["hosts"]["node2"]["ansible_connection"] = "fixture_unreachable"
        (self.lab / "node2/connection-lost").write_text("disconnected\n", encoding="utf-8")
        stats, _ = self.run_play("rolling.yml", expected=1)
        self.assertGreaterEqual(stats["node2"]["unreachable"], 1)
        self.assertEqual(self.read("node2", "config"), "release=v1\n")
        self.assertNotIn("node3", stats)

    def test_failure_percentage_requires_exceeding_not_reaching_threshold(self):
        below, _ = self.run_play("threshold.yml", variables={"threshold": 49}, expected=1)
        self.assertNotIn("node3", below)
        at, _ = self.run_play("threshold.yml", variables={"threshold": 50}, expected=1)
        self.assertIn("node3", at)
        self.assertEqual(self.read("node3", "reached"), "reached\n")

    def test_run_once_is_per_serial_batch_not_global(self):
        self.run_play("run-once.yml")
        self.assertTrue(all((self.lab / host / "batch-once").is_file() for host in HOSTS))
        self.assertTrue((self.lab / "node1/singleton").is_file())
        self.assertFalse((self.lab / "node2/singleton").exists())
        self.assertFalse((self.lab / "node3/singleton").exists())


if __name__ == "__main__":
    unittest.main()
