#!/usr/bin/env python3
"""Synthetic release recovery after actual cross-job artifact admission.

Source-only lab, not a production deployer, fencing service or crash-durable
distributed journal. Local files represent remote nodes/data/external effects.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
import os
from pathlib import Path
import stat
import sys
import tempfile
import unittest
from zipfile import ZipFile, ZipInfo

from cicd_artifact import check_metadata, context, payload_bytes, validate_payload, zip_payload

ACCEPTED_PAYLOAD = None
HOSTS = ("node1", "node2", "node3")


class InterruptedRelease(RuntimeError):
    pass


class DeliveryLab:
    def __init__(self, root, payload):
        self.root, self.payload = root, payload
        self.digest = hashlib.sha256(payload).hexdigest()
        self.old = hashlib.sha256(b"synthetic-v1").hexdigest()
        self.journal = root / "outcomes.jsonl"
        self.data = {"schema": 1, "rows": 100, "external_events": 0}
        for host in HOSTS:
            self.write(host, {"active": self.old, "traffic": "ready", "effects": {}, "activations": 0})

    def path(self, host):
        if host not in HOSTS:
            raise ValueError("unexpected target")
        return self.root / (host + ".json")

    def read(self, host):
        return json.loads(self.path(host).read_text(encoding="utf-8"))

    def write(self, host, value):
        self.path(host).write_text(json.dumps(value, sort_keys=True), encoding="utf-8")

    def record(self, host, event):
        with self.journal.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"host": host, "event": event, "digest": self.digest}) + "\n")
            stream.flush()
            os.fsync(stream.fileno())

    def migrate(self):
        if self.data["schema"] == 1:
            self.data.update(schema=2, rows=101, external_events=1)

    def deploy(self, *, fail_host="", lose_response=False, recovery_fails=False, key="release-v2"):
        for host in HOSTS:
            observed = self.read(host)
            if observed["active"] not in (self.old, self.digest):
                raise InterruptedRelease("unknown active version")
            previous = observed["effects"].get(key)
            if previous and previous != self.digest:
                raise InterruptedRelease("idempotency key belongs to different bytes")
        self.migrate()
        for host in HOSTS:
            state = self.read(host)  # Missing/unknown target blocks before later writes.
            previous = state["effects"].get(key)
            if previous and previous != self.digest:
                raise InterruptedRelease("idempotency key belongs to different bytes")
            if state["active"] == self.digest and state["traffic"] == "ready":
                continue
            self.record(host, "launch-intent")
            state["traffic"] = "excluded"
            self.write(host, state)
            if not previous:
                state["effects"][key] = self.digest
                state["activations"] += 1
                state["active"] = self.digest
                self.write(host, state)
            if host == fail_host:
                if lose_response:
                    raise InterruptedRelease("response lost after actual activation")
                self.record(host, "recovery-failed" if recovery_fails else "acceptance-failed")
                raise InterruptedRelease("halt next batch; preserve exclusion and current data")
            if self.read(host)["active"] != self.digest:
                raise InterruptedRelease("actual running digest mismatch")
            state["traffic"] = "ready"
            self.write(host, state)
            self.record(host, "accepted")

    def rollback(self, *, writer_max_schema=1, queue_compatible=False):
        if self.data["schema"] > writer_max_schema or not queue_compatible:
            raise InterruptedRelease("old writer or queue compatibility unproven")
        for host in HOSTS:
            state = self.read(host)
            state.update(active=self.old, traffic="ready")
            self.write(host, state)
            self.record(host, "compatible-code-reversal")


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="devops-delivery-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.value = ACCEPTED_PAYLOAD
        self.lab = DeliveryLab(self.root, self.value)

    def test_same_admitted_bytes_reach_all_targets(self):
        self.lab.deploy()
        self.assertTrue(all(self.lab.read(host)["active"] == hashlib.sha256(self.value).hexdigest() for host in HOSTS))
        self.assertTrue(all(self.lab.read(host)["traffic"] == "ready" for host in HOSTS))

    def test_repeating_release_does_not_repeat_activation_or_external_effect(self):
        self.lab.deploy()
        before = [self.lab.path(host).read_bytes() for host in HOSTS]
        self.lab.deploy()
        self.assertEqual([self.lab.path(host).read_bytes() for host in HOSTS], before)
        self.assertEqual(self.lab.data, {"schema": 2, "rows": 101, "external_events": 1})
        self.assertTrue(all(self.lab.read(host)["activations"] == 1 for host in HOSTS))

    def test_partial_failure_stops_later_node_and_preserves_exclusion(self):
        with self.assertRaises(InterruptedRelease):
            self.lab.deploy(fail_host="node2")
        self.assertEqual(self.lab.read("node1")["traffic"], "ready")
        self.assertEqual(self.lab.read("node2")["active"], self.lab.digest)
        self.assertEqual(self.lab.read("node2")["traffic"], "excluded")
        self.assertEqual(self.lab.read("node3")["active"], self.lab.old)
        self.assertEqual(self.lab.data["rows"], 101)

    def test_lost_response_reconciles_actual_effect_before_replay(self):
        with self.assertRaises(InterruptedRelease):
            self.lab.deploy(fail_host="node2", lose_response=True)
        events = [json.loads(line) for line in self.lab.journal.read_text().splitlines()]
        self.assertEqual([item["event"] for item in events if item["host"] == "node2"], ["launch-intent"])
        self.assertEqual(self.lab.read("node2")["activations"], 1)
        self.lab.deploy()
        self.assertTrue(all(self.lab.read(host)["traffic"] == "ready" for host in HOSTS))
        self.assertTrue(all(self.lab.read(host)["activations"] == 1 for host in HOSTS))
        self.assertEqual(self.lab.data["external_events"], 1)
        self.assertIn('"launch-intent"', self.lab.journal.read_text())

    def test_failed_recovery_is_visible_and_keeps_later_node_untouched(self):
        with self.assertRaises(InterruptedRelease):
            self.lab.deploy(fail_host="node2", recovery_fails=True)
        self.assertIn('"recovery-failed"', self.lab.journal.read_text())
        self.assertEqual(self.lab.read("node2")["traffic"], "excluded")
        self.assertEqual(self.lab.read("node3")["active"], self.lab.old)

    def test_old_binary_rollback_refused_after_new_schema_and_writes(self):
        with self.assertRaises(InterruptedRelease):
            self.lab.deploy(fail_host="node2")
        self.lab.data["rows"] += 143
        before = [self.lab.path(host).read_bytes() for host in HOSTS], copy.deepcopy(self.lab.data)
        with self.assertRaises(InterruptedRelease):
            self.lab.rollback()
        self.assertEqual(([self.lab.path(host).read_bytes() for host in HOSTS], self.lab.data), before)

    def test_compatible_code_reversal_retains_current_data_and_effects(self):
        self.lab.deploy()
        before = copy.deepcopy(self.lab.data)
        self.lab.rollback(writer_max_schema=2, queue_compatible=True)
        self.assertTrue(all(self.lab.read(host)["active"] == self.lab.old for host in HOSTS))
        self.assertEqual(self.lab.data, before)

    def test_unknown_target_and_conflicting_idempotency_key_block_promotion(self):
        self.lab.path("node2").unlink()
        with self.assertRaises(FileNotFoundError):
            self.lab.deploy()
        self.assertEqual(self.lab.data["schema"], 1)
        self.assertEqual(self.lab.read("node1")["activations"], 0)
        self.assertEqual(self.lab.read("node3")["active"], self.lab.old)
        state = self.lab.read("node1")
        state["effects"]["release-v2"] = "different-bytes"
        self.lab.write("node1", state)
        with self.assertRaises(InterruptedRelease):
            self.lab.deploy()

    def test_tampered_payload_or_forged_context_rejected(self):
        ctx = context()
        digest = hashlib.sha256(self.value).hexdigest()
        for value, expected in ((self.value + b"x", digest), (self.value.replace(b"synthetic-v2", b"synthetic-v9"), digest), (payload_bytes(dict(ctx, attempt="999")), digest)):
            with self.assertRaises(ValueError):
                validate_payload(value, expected, ctx)

    def test_archives_refuse_traversal_links_duplicates_and_extra_members(self):
        for names in (("../payload.json",), ("/payload.json",), ("payload.json", "payload.json"), ("payload.json", "other"), ("link",)):
            stream = io.BytesIO()
            with ZipFile(stream, "w") as archive:
                for name in names:
                    info = ZipInfo(name)
                    if name == "link":
                        info.external_attr = (stat.S_IFLNK | 0o777) << 16
                    archive.writestr(info, self.value)
            with self.assertRaises(ValueError):
                zip_payload(stream.getvalue())

    def test_archive_and_payload_digest_domains_are_distinct(self):
        stream = io.BytesIO()
        with ZipFile(stream, "w") as archive:
            archive.writestr("payload.json", self.value)
        archive_value = stream.getvalue()
        self.assertNotEqual(hashlib.sha256(archive_value).hexdigest(), hashlib.sha256(self.value).hexdigest())
        self.assertEqual(zip_payload(archive_value), self.value)
        with self.assertRaises(ValueError):
            validate_payload(self.value, hashlib.sha256(archive_value).hexdigest(), context())

    def test_foreign_or_stale_artifact_identity_is_rejected(self):
        ctx = context()
        artifact = {"id": 7, "name": f"cicd-fixture-{ctx['run_id']}-{ctx['attempt']}", "expired": False, "digest": "sha256:" + "a" * 64,
                    "created_at": "2026-10-30T10:01:00Z", "workflow_run": {"id": int(ctx["run_id"]), "repository_id": int(ctx["repository_id"]), "head_repository_id": int(ctx["head_repository_id"]), "head_sha": ctx["event_sha"]}}
        run = {"id": int(ctx["run_id"]), "run_attempt": int(ctx["attempt"]), "path": ".github/workflows/cicd-operations.yml", "event": ctx["event"], "head_sha": ctx["event_sha"], "run_started_at": "2026-10-30T10:00:00Z"}
        check_metadata(artifact, run, ctx, 7, "a" * 64)
        for key, value in (("id", 8), ("expired", True), ("name", "latest"), ("digest", "sha256:" + "b" * 64), ("created_at", "2026-10-30T09:59:00Z")):
            changed = copy.deepcopy(artifact)
            changed[key] = value
            with self.assertRaises(ValueError):
                check_metadata(changed, run, ctx, 7, "a" * 64)
        for key in ("id", "repository_id", "head_repository_id", "head_sha"):
            changed = copy.deepcopy(artifact)
            changed["workflow_run"][key] = "wrong"
            with self.assertRaises(ValueError):
                check_metadata(changed, run, ctx, 7, "a" * 64)
        for key in ("run_attempt", "path", "event", "head_sha"):
            changed = copy.deepcopy(run)
            changed[key] = "wrong"
            with self.assertRaises(ValueError):
                check_metadata(artifact, changed, ctx, 7, "a" * 64)


if __name__ == "__main__":
    path = Path(sys.argv.pop(1))
    ACCEPTED_PAYLOAD = path.read_bytes()
    validate_payload(ACCEPTED_PAYLOAD, os.environ["FIXTURE_PAYLOAD_DIGEST"], context())
    unittest.main()
