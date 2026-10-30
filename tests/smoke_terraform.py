#!/usr/bin/env python3
"""Actual pinned Terraform/OpenTofu against synthetic local objects and HTTP state.

Linux x86_64 only; failures/missing tools never turn into native-test skips.
Downloads official checksum-pinned CLI/provider artifacts, then uses an offline
provider mirror and an owned loopback backend. No cloud credentials or targets.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.request import urlopen
import uuid
from zipfile import ZipFile

from iac_fixture_backend import StateBackend

TOOLS = {
    "terraform": ("1.17.1", "https://releases.hashicorp.com/terraform/1.17.1/terraform_1.17.1_linux_amd64.zip", "4638628058e71a55212b1c563712eac03b902128f40740f3dc8174df12135061"),
    "tofu": ("1.13.2", "https://github.com/opentofu/opentofu/releases/download/v1.13.2/tofu_1.13.2_linux_amd64.zip", "723bebb0df8411daff1e5fc3862e28ff5581fe5634087f4c29a9aa41d78208b5"),
}
PROVIDER_SHA = "40d9dfc9c549e406b5aab73c023aa485633c1b6b730c933d7bcc2fa67fd1ae6e"
SELECTED_TOOL = None


def download(url, digest):
    with urlopen(url, timeout=90) as response:
        value = response.read(80 * 1024 * 1024 + 1)
    if len(value) > 80 * 1024 * 1024 or hashlib.sha256(value).hexdigest() != digest:
        raise RuntimeError("official fixture artifact failed size/checksum verification")
    return value


class NativeIaCTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not sys.platform.startswith("linux") or platform.machine().lower() not in ("x86_64", "amd64"):
            raise RuntimeError("native IaC fixture requires disposable Linux x86_64")
        cls.tools_temp = tempfile.TemporaryDirectory(prefix="devops-iac-tools-")
        cls.addClassCleanup(cls.tools_temp.cleanup)
        cls.tools_root = Path(cls.tools_temp.name).resolve()
        version, url, checksum = TOOLS[SELECTED_TOOL]
        with ZipFile(io.BytesIO(download(url, checksum))) as archive:
            cli_data = archive.read(SELECTED_TOOL)
        cls.cli = cls.tools_root / SELECTED_TOOL
        cls.cli.write_bytes(cli_data)
        cls.cli.chmod(0o700)
        mirror = cls.tools_root / "mirror/registry.terraform.io/hashicorp/local"
        mirror.mkdir(parents=True)
        provider = "terraform-provider-local_2.5.3_linux_amd64.zip"
        (mirror / provider).write_bytes(download("https://releases.hashicorp.com/terraform-provider-local/2.5.3/" + provider, PROVIDER_SHA))
        cls.config = cls.tools_root / "isolated.tfrc"
        cls.config.write_text('provider_installation {\n filesystem_mirror {\n path = ' + json.dumps(str(cls.tools_root / "mirror")) + '\n include = ["registry.terraform.io/hashicorp/local"]\n }\n}\ndisable_checkpoint = true\n', encoding="utf-8")
        cls.base_env = {key: value for key, value in os.environ.items() if not key.startswith(("TF_", "TOFU_"))}
        cls.base_env.update({"TF_CLI_CONFIG_FILE": str(cls.config), "TOFU_CLI_CONFIG_FILE": str(cls.config), "TF_IN_AUTOMATION": "1", "CHECKPOINT_DISABLE": "1"})
        result = subprocess.run([str(cls.cli), "version", "-json"], env=cls.base_env, capture_output=True, text=True, timeout=20, check=True)
        if json.loads(result.stdout)["terraform_version"] != version:
            raise RuntimeError("native executable version mismatch")
        print(f"Verified {SELECTED_TOOL} {version}; local provider 2.5.3; synthetic HTTP backend", flush=True)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="devops-iac-case-")
        self.addCleanup(self.temp.cleanup)
        self.lab = Path(self.temp.name).resolve()
        self.lab.chmod(0o700)
        self.backend = StateBackend()
        self.addCleanup(self.backend.close)
        self.env = dict(self.base_env)
        self.env.update({"TF_HTTP_RETRY_MAX": "0", "TF_HTTP_RETRY_WAIT_MIN": "1"})
        self.lockfile = self.lab / ".terraform.lock.hcl"
        self.lockfile.write_text('provider "registry.terraform.io/hashicorp/local" {\n version = "2.5.3"\n constraints = "2.5.3"\n hashes = ["zh:' + PROVIDER_SHA + '"]\n}\n', encoding="utf-8")
        self.write_config()
        self.init(self.backend)

    def write_config(self, *, resource="managed", moved=False, provisioner=None):
        data = {
            "terraform": {"backend": {"http": {}}, "required_providers": {"local": {"source": "registry.terraform.io/hashicorp/local", "version": "2.5.3"}}},
            "variable": {"release": {"type": "string", "default": "v1"}},
            "resource": {"local_file": {resource: {"filename": str(self.lab / "object.txt"), "content": "${var.release}", "file_permission": "0600"}}},
        }
        if moved:
            data["moved"] = [{"from": "local_file.managed", "to": "local_file.renamed"}]
        if provisioner:
            data["resource"]["terraform_data"] = {"step": {
                "input": "synthetic", "depends_on": ["local_file." + resource],
                "provisioner": [{"local-exec": {"interpreter": [sys.executable, "-c"], "command": provisioner}}],
            }}
        (self.lab / "main.tf.json").write_text(json.dumps(data), encoding="utf-8")

    def run_cli(self, *args, expected=(0,)):
        result = subprocess.run([str(self.cli), *args], cwd=self.lab, env=self.env, capture_output=True, text=True, timeout=100)
        self.assertIn(result.returncode, expected, result.stdout[-9000:] + result.stderr[-4000:])
        return result

    def init(self, backend, *, mode=None):
        args = ["init", "-input=false", "-no-color", "-lockfile=readonly",
                "-backend-config=address=" + backend.url + "/state",
                "-backend-config=lock_address=" + backend.url + "/lock",
                "-backend-config=unlock_address=" + backend.url + "/lock"]
        if mode == "migrate":
            args.extend(["-migrate-state", "-force-copy"])
        elif mode == "reconfigure":
            args.append("-reconfigure")
        self.run_cli(*args)

    def plan(self, filename="review.plan", *, release="v1", options=(), expected=(2,)):
        return self.run_cli("plan", "-input=false", "-no-color", "-detailed-exitcode", "-out=" + filename, "-var=release=" + release, *options, expected=expected)

    def apply(self, filename="review.plan", *, expected=(0,)):
        return self.run_cli("apply", "-input=false", "-no-color", filename, expected=expected)

    def provision(self, release="v1"):
        self.plan(release=release)
        self.apply()
        self.assertEqual((self.lab / "object.txt").read_text(), release)

    def state(self):
        return json.loads(self.run_cli("state", "pull").stdout)

    def addresses(self, state=None):
        state = state if state is not None else self.state()
        return {resource["type"] + "." + resource["name"] for resource in state.get("resources", [])}

    def test_saved_plan_converges_and_next_full_plan_is_empty(self):
        self.run_cli("validate", "-no-color")
        self.provision()
        self.assertEqual(self.addresses(), {"local_file.managed"})
        before = self.backend.snapshot()
        self.plan("second.plan", expected=(0,))
        self.assertEqual(before, self.backend.snapshot())
        self.assertIsNone(self.backend.lock)

    def test_refreshed_drift_and_disabled_refresh_blind_spot(self):
        self.provision()
        (self.lab / "object.txt").unlink()
        before = self.backend.snapshot()
        self.plan("blind.plan", options=("-refresh=false",), expected=(0,))
        self.plan("drift.plan")
        detail = json.loads(self.run_cli("show", "-json", "drift.plan").stdout)
        self.assertTrue(any(item["address"] == "local_file.managed" and "create" in item["change"]["actions"] for item in detail["resource_changes"]))
        self.assertFalse((self.lab / "object.txt").exists())
        self.assertEqual(before, self.backend.snapshot(), "planning must not be counted as persisted reconciliation")

    def test_refresh_only_persists_bindings_without_recreating_object(self):
        self.provision()
        before = self.state()
        (self.lab / "object.txt").unlink()
        self.plan("refresh.plan", options=("-refresh-only",))
        self.assertIn("local_file.managed", self.addresses())
        self.apply("refresh.plan")
        after = self.state()
        self.assertNotIn("local_file.managed", self.addresses(after))
        self.assertEqual(after["lineage"], before["lineage"])
        self.assertGreater(after["serial"], before["serial"])
        self.assertFalse((self.lab / "object.txt").exists())
        self.plan("repair.plan")

    def test_stale_saved_plan_is_rejected_after_intervening_state_write(self):
        self.provision()
        self.plan("older.plan", release="v2")
        self.plan("newer.plan", release="v3")
        self.apply("newer.plan")
        before = self.backend.snapshot()
        result = self.apply("older.plan", expected=(1,))
        self.assertIn("stale", (result.stdout + result.stderr).lower())
        self.assertEqual(self.backend.snapshot(), before)
        self.assertEqual((self.lab / "object.txt").read_text(), "v3")

    def test_state_push_refuses_foreign_lineage_and_older_serial(self):
        self.provision()
        original = self.state()
        self.assertGreaterEqual(original["serial"], 1)
        for field, value in (("lineage", str(uuid.uuid4())), ("serial", original["serial"] - 1)):
            with self.subTest(field=field):
                candidate = dict(original, **{field: value})
                path = self.lab / "candidate.tfstate"
                path.write_text(json.dumps(candidate), encoding="utf-8")
                path.chmod(0o600)
                before = self.backend.snapshot()
                self.run_cli("state", "push", str(path), expected=(1,))
                self.assertEqual(self.backend.snapshot(), before)

    def test_live_owner_lock_blocks_competing_plan(self):
        ready, release = self.lab / "ready", self.lab / "release"
        code = f"import pathlib,time; pathlib.Path({str(ready)!r}).write_text('ready'); deadline=time.monotonic()+45\nwhile not pathlib.Path({str(release)!r}).exists():\n if time.monotonic()>deadline: raise RuntimeError('fixture hold deadline')\n time.sleep(0.1)"
        self.write_config(provisioner=code)
        self.plan()
        process = subprocess.Popen([str(self.cli), "apply", "-input=false", "-no-color", "review.plan"], cwd=self.lab, env=self.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 30
            while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertTrue(ready.exists(), "owned apply did not reach locked hold point")
            self.assertIsNone(process.poll())
            lock_id = self.backend.lock["ID"]
            result = self.run_cli("plan", "-input=false", "-no-color", "-lock-timeout=1s", expected=(1,))
            self.assertIn("lock", (result.stdout + result.stderr).lower())
            self.assertEqual(self.backend.lock["ID"], lock_id)
            release.write_text("release")
            stdout, stderr = process.communicate(timeout=40)
            self.assertEqual(process.returncode, 0, stdout + stderr)
            self.assertIsNone(self.backend.lock)
        finally:
            release.write_text("release")
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=10)

    def test_force_unlock_only_matches_exact_synthetic_stale_id(self):
        self.provision()
        stale = str(uuid.uuid4())
        with self.backend.guard:
            self.backend.lock = {"ID": stale, "Operation": "synthetic-ended-run", "Who": "fixture", "Version": TOOLS[SELECTED_TOOL][0], "Created": "2026-10-30T00:00:00Z", "Path": "synthetic"}
        self.run_cli("force-unlock", "-force", str(uuid.uuid4()), expected=(1,))
        self.assertEqual(self.backend.lock["ID"], stale)
        self.run_cli("force-unlock", "-force", stale)
        self.assertIsNone(self.backend.lock)

    def test_partial_apply_preserves_success_then_fresh_forward_repair(self):
        self.write_config(provisioner="import sys; sys.exit(7)")
        self.plan()
        self.apply(expected=(1,))
        partial = self.state()
        self.assertEqual((self.lab / "object.txt").read_text(), "v1")
        self.assertIn("local_file.managed", self.addresses(partial))
        tainted = next(item for item in partial["resources"] if item["type"] == "terraform_data")
        self.assertEqual(tainted["instances"][0]["status"], "tainted")
        before_file = (self.lab / "object.txt").stat().st_mtime_ns
        self.write_config(provisioner="pass")
        self.plan("repair.plan")
        detail = json.loads(self.run_cli("show", "-json", "repair.plan").stdout)
        kept = next(item for item in detail["resource_changes"] if item["address"] == "local_file.managed")
        self.assertEqual(kept["change"]["actions"], ["no-op"])
        self.apply("repair.plan")
        self.assertEqual((self.lab / "object.txt").stat().st_mtime_ns, before_file)
        self.plan("clean.plan", expected=(0,))

    def test_failed_state_persistence_recovers_exact_error_snapshot(self):
        self.provision()
        before = self.state()
        self.plan("change.plan", release="v2")
        self.backend.reject_writes = True
        self.apply("change.plan", expected=(1,))
        self.assertEqual((self.lab / "object.txt").read_text(), "v2")
        self.assertEqual(json.loads(self.backend.snapshot())["serial"], before["serial"])
        recovery = self.lab / "errored.tfstate"
        self.assertTrue(recovery.is_file(), "CLI did not preserve its recovery snapshot")
        recovery.chmod(0o600)
        recovered = json.loads(recovery.read_text())
        self.assertEqual(recovered["lineage"], before["lineage"])
        self.assertIn("local_file.managed", self.addresses(recovered))
        self.backend.reject_writes = False
        self.assertIsNone(self.backend.lock)
        self.run_cli("state", "push", str(recovery))
        self.assertEqual(self.state()["lineage"], recovered["lineage"])
        self.plan("after-recovery.plan", release="v2", expected=(0,))

    def test_lost_upload_response_can_hide_a_successful_state_commit(self):
        self.provision()
        self.plan("ambiguous.plan", release="v2")
        self.backend.commit_then_error = True
        self.apply("ambiguous.plan", expected=(1,))
        self.backend.commit_then_error = False
        self.assertEqual((self.lab / "object.txt").read_text(), "v2")
        persisted = json.loads(self.backend.snapshot())
        instance = next(item for item in persisted["resources"] if item["type"] == "local_file")["instances"][0]
        self.assertEqual(instance["attributes"]["content"], "v2")
        # Reconcile committed state; do not blindly replay apply/push on error.
        self.plan("observed.plan", release="v2", expected=(0,))

    def test_moved_address_preserves_object_and_removal_only_forgets_binding(self):
        self.provision()
        before = (self.lab / "object.txt").stat().st_mtime_ns
        self.write_config(resource="renamed", moved=True)
        self.plan("move.plan", expected=(0, 2))
        detail = json.loads(self.run_cli("show", "-json", "move.plan").stdout)
        changed = next(item for item in detail["resource_changes"] if item["address"] == "local_file.renamed")
        self.assertEqual(changed["previous_address"], "local_file.managed")
        self.assertEqual(changed["change"]["actions"], ["no-op"])
        self.apply("move.plan")
        self.assertEqual(self.addresses(), {"local_file.renamed"})
        self.assertEqual((self.lab / "object.txt").stat().st_mtime_ns, before)
        self.run_cli("state", "rm", "local_file.renamed")
        self.assertTrue((self.lab / "object.txt").is_file())
        self.assertNotIn("local_file.renamed", self.addresses())
        self.plan("unmanaged.plan")

    def test_backend_migration_preserves_lineage_and_object(self):
        self.provision()
        original = self.state()
        destination = StateBackend()
        self.addCleanup(destination.close)
        self.init(destination, mode="migrate")
        migrated = self.state()
        self.assertEqual(migrated["lineage"], original["lineage"])
        self.assertEqual(self.addresses(migrated), self.addresses(original))
        self.assertIsNotNone(self.backend.snapshot(), "source copy still needs operational retirement")
        self.assertIsNotNone(destination.snapshot())
        self.assertEqual((self.lab / "object.txt").read_text(), "v1")
        self.plan("migrated.plan", expected=(0,))

    def test_reconfigure_empty_backend_is_not_a_migration(self):
        self.provision()
        original = self.backend.snapshot()
        destination = StateBackend()
        self.addCleanup(destination.close)
        self.init(destination, mode="reconfigure")
        self.plan("wrong-backend.plan")
        self.assertEqual(self.backend.snapshot(), original)
        self.assertTrue((self.lab / "object.txt").is_file())
        self.assertFalse(destination.snapshot() and json.loads(destination.snapshot()).get("resources"))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tool", choices=TOOLS)
    arguments, rest = parser.parse_known_args()
    SELECTED_TOOL = arguments.tool
    unittest.main(argv=[sys.argv[0], *rest])
