from __future__ import annotations

import copy
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock
from contextlib import redirect_stdout

from test_platform import operation, bind_approvals

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent
spec = importlib.util.spec_from_file_location("autonomy_test_gate", ROOT/"devops-platform-contracts/scripts/operation_gate.py")
G = importlib.util.module_from_spec(spec); spec.loader.exec_module(G)
A = G.AUTONOMY
NOW = datetime(2026, 8, 17, 10, 15, tzinfo=timezone.utc)
POLICY, BINDING = G.load_registered_policy("default-policy.json")
IDENTITY = "authority-example-lab"


def request(risk="R2", environment="lab"):
    result = operation(risk=risk, approvals=0)
    result["target"]["environment"] = environment
    result["change"]["irreversible"] = False
    if risk in {"R3", "R4"}:
        result["execution"]["change_lock_ref"] = "lock:exact-target-fixture"
    return result


def record(req, mode="balanced"):
    result = {"schema_version": "1.0", "authorization_id": IDENTITY, "status": "active", "mode": mode,
              "policy": req["policy"], "target": copy.deepcopy(req["target"]), "executor": req["execution"]["executor"],
              "actions": [req["change"]["action"]], "scope": list(req["change"]["scope"]),
              "data_classifications": [req["data_classification"]], "allow_stateful": req["change"]["stateful"],
              "allow_external_side_effects": req["change"]["external_side_effects"],
              "window_start": req["execution"]["window_start"], "window_end": req["execution"]["window_end"],
              "trusted_environment": None if mode != "full-auto" else {"isolation_ref": "lab:isolated", "credential_scope_ref": "role:bounded", "owner_evidence_ref": "ticket:scope-001"},
              "authorizations": []}
    authorize(result)
    return result


def authorize(value, actors=(("user:owner", "service-owner"),)):
    value["authorizations"] = [{"approver": actor, "role": role, "payload_digest": A.payload_digest(value),
                               "approved_at": value["window_start"], "expires_at": value["window_end"], "evidence_ref": "ticket:authority-001"} for actor, role in actors]


def recovery(req):
    req["change"]["stateful"] = True
    req["recovery"] = {"required": True, "method": "isolated restore", "artifact_ref": "backup:fixture-001",
                       "restore_tested_at": "2026-08-17T09:30:00Z", "rpo_minutes": 0, "rto_minutes": 5}


class AutonomyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="autonomy-unit-", dir=WORK)
        self.store = Path(self.temporary.name)
        self.assertTrue(self.store.resolve().is_relative_to(WORK.resolve()))
        self.addCleanup(self.temporary.cleanup)

    def bind(self, req, value):
        (self.store/(IDENTITY+".json")).write_text(json.dumps(value), encoding="utf-8")
        req["autonomy"] = {"mode": value["mode"], "authorization_id": IDENTITY, "authorization_digest": A.digest(value)}

    def validate(self, req, policy=POLICY, binding=BINDING, now=NOW):
        return G.validate(req, policy, binding, now, authority_dir=self.store)

    def test_safe_default_keeps_read_and_low_risk_without_confirmation(self):
        for risk in ("R0", "R1"):
            req = request(risk)
            self.assertEqual(self.validate(req), [])
            req["autonomy"] = {"mode": "safe", "authorization_id": None, "authorization_digest": None}
            self.assertEqual(self.validate(req), [])
        self.assertTrue(any("approval" in reason for reason in self.validate(request("R2"))))

    def test_four_mode_ceilings_and_explicit_higher_risk_admission(self):
        for mode, ceiling in (("balanced", 2), ("semi-auto", 3), ("full-auto", 4)):
            for level in range(5):
                req = request("R"+str(level))
                self.bind(req, record(req, mode))
                reasons = self.validate(req)
                if level <= ceiling:
                    self.assertEqual(reasons, [], (mode, level, reasons))
                else:
                    self.assertTrue(any("approval" in item for item in reasons), (mode, level, reasons))
                    req["approvals"] = operation(risk="R"+str(level), approvals=1)["approvals"]
                    bind_approvals(req)  # Synthetic exact re-approval after all operation facts are set.
                    self.assertEqual(self.validate(req), [])

    def test_balanced_does_not_reclassify_a_production_deploy(self):
        req = request("R2", environment="production")
        self.bind(req, record(req))
        self.assertTrue(any("production" in item for item in self.validate(req)))
        req["change"]["risk"] = "R3"
        self.assertTrue(any("approval" in item for item in self.validate(req)))

    def test_semi_auto_production_with_declared_scope_and_lock(self):
        req = request("R3", environment="production")
        self.bind(req, record(req, "semi-auto"))
        self.assertEqual(self.validate(req), [])
        req["execution"]["change_lock_ref"] = None
        self.assertTrue(any("lock" in item for item in self.validate(req)))

    def test_full_auto_stateful_r4_requires_trust_and_recovery(self):
        req = request("R4"); recovery(req)
        value = record(req, "full-auto"); self.bind(req, value)
        self.assertEqual(self.validate(req), [])
        for missing in ("artifact_ref", "restore_tested_at", "rpo_minutes", "rto_minutes"):
            changed = copy.deepcopy(req); changed["recovery"][missing] = None
            self.assertTrue(self.validate(changed), missing)
        value["trusted_environment"] = None; authorize(value); self.bind(req, value)
        self.assertTrue(self.validate(req))

    def test_destructive_and_irreversible_require_separate_exact_approval(self):
        for flag in ("destructive", "irreversible"):
            req = request("R4"); recovery(req); req["change"][flag] = True
            self.bind(req, record(req, "full-auto"))
            self.assertTrue(any("approval" in item for item in self.validate(req)))
            req["approvals"] = operation(risk="R4", approvals=1)["approvals"]
            bind_approvals(req)  # Synthetic exact re-approval after all operation facts are set.
            self.assertEqual(self.validate(req), [])
            req["approvals"][0]["plan_digest"] = "sha256:"+"f"*64
            self.assertTrue(self.validate(req))
        req = request("R2"); req["change"]["irreversible"] = True
        self.assertTrue(any("R4" in item for item in self.validate(req)))

    def test_scope_action_data_and_flags_outside_grant_need_confirmation(self):
        base = request()
        value = record(base)
        for mutate in (
            lambda r: r["change"].update(scope=["service:other"]),
            lambda r: r["change"].update(action="other_action"),
            lambda r: r.update(data_classification="restricted"),
            lambda r: r["change"].update(stateful=True),
        ):
            req = copy.deepcopy(base); self.bind(req, value); mutate(req)
            self.assertTrue(any("approval" in item for item in self.validate(req)))
            req["approvals"] = operation(approvals=1)["approvals"]
            bind_approvals(req)  # Synthetic exact re-approval after all operation facts are set.
            self.assertEqual(self.validate(req), [])
        req = request(); value = record(req); value["allow_external_side_effects"] = False
        authorize(value); self.bind(req, value)
        self.assertTrue(any("approval" in item for item in self.validate(req)))

    def test_unknown_or_null_mode_and_missing_irreversibility_fail_closed(self):
        for selection in (None, {}, {"mode": "typo"}, {"mode": "safe", "authorization_id": IDENTITY, "authorization_digest": None}):
            req = request("R0"); req["autonomy"] = selection
            self.assertTrue(self.validate(req))
        req = request(); self.bind(req, record(req)); del req["change"]["irreversible"]
        self.assertTrue(self.validate(req))

    def test_target_executor_profile_and_policy_drift_never_fall_back(self):
        base = request()
        for mutate in (
            lambda r: r["target"].update(name="other"),
            lambda r: r["target"].update(environment="production"),
            lambda r: r["target"].update(owner="other-owner"),
            lambda r: r["target"].update(profile_digest="sha256:"+"f"*64),
            lambda r: r["execution"].update(executor="service:other"),
            lambda r: r["policy"].update(digest="sha256:"+"f"*64),
            lambda r: r["autonomy"].update(mode="full-auto"),
        ):
            req = copy.deepcopy(base); self.bind(req, record(req)); mutate(req)
            req["approvals"] = operation(approvals=1)["approvals"]
            bind_approvals(req)  # Synthetic exact re-approval after all operation facts are set.
            self.assertTrue(self.validate(req))

    def test_expiry_revocation_change_and_deletion_fail_closed(self):
        req = request(); value = record(req); self.bind(req, value)
        end = datetime(2026, 8, 17, 11, tzinfo=timezone.utc)
        self.assertTrue(self.validate(req, now=end))
        self.assertTrue(self.validate(req, now=NOW-timedelta(hours=1)))
        path = self.store/(IDENTITY+".json")
        value["status"] = "revoked"; path.write_text(json.dumps(value), encoding="utf-8")
        self.assertTrue(self.validate(req))
        path.unlink()
        self.assertTrue(self.validate(req))

    def test_changed_command_plan_inside_same_authority_does_not_ask_again(self):
        req = request(); self.bind(req, record(req))
        self.assertEqual(self.validate(req), [])
        req["change"]["plan_digest"] = "sha256:"+"b"*64
        req["operation_id"] = "ops-next-000001"
        req["execution"]["idempotency_key"] = "next-operation-001"
        self.assertEqual(self.validate(req), [])
        req["execution"]["window_end"] = "2026-08-17T11:01:00Z"
        self.assertTrue(self.validate(req))

    def test_issuer_payload_ttl_and_separation_cannot_be_forged_by_request(self):
        for mutate in (
            lambda v: v["authorizations"][0].update(approver="service:codex"),
            lambda v: v["authorizations"][0].update(payload_digest="sha256:"+"f"*64),
            lambda v: v.update(scope=["service:other"]),
            lambda v: v.update(window_end="2026-08-17T13:01:00Z"),
            lambda v: v.update(authorizations=[]),
            lambda v: v.update(status="draft"),
        ):
            req = request(); value = record(req); mutate(value); self.bind(req, value)
            self.assertTrue(self.validate(req))

    def test_stricter_policy_caps_modes_and_cannot_be_weakened(self):
        policy, binding = G.load_registered_policy("enterprise-policy.json")
        req = operation(policy_name="enterprise-policy.json", approvals=0)
        req["change"]["irreversible"] = False
        self.bind(req, record(req))
        self.assertTrue(self.validate(req, policy, binding))
        parent = copy.deepcopy(POLICY); parent["autonomy"]["maximum_mode"] = "balanced"
        with self.assertRaises(ValueError): G.ensure_not_weaker(parent, POLICY, "child")
        strict = copy.deepcopy(POLICY); strict["autonomy"]["allow_production"] = False
        with self.assertRaises(ValueError): G.ensure_not_weaker(strict, POLICY, "child")

    def test_delegated_stateful_r3_cannot_skip_recovery_or_use_future_proof(self):
        req = request("R3"); recovery(req)
        self.bind(req, record(req, "semi-auto"))
        self.assertEqual(self.validate(req), [])
        req["recovery"]["required"] = False
        self.assertTrue(self.validate(req))
        req["recovery"]["required"] = True
        req["recovery"]["restore_tested_at"] = "2026-08-18T10:00:00Z"
        self.assertTrue(self.validate(req))

    def test_hard_policy_denial_and_exceptions_are_not_auto_waivers(self):
        req = request(); req["change"]["action"] = "untrusted_content_authority"
        self.bind(req, record(req))
        self.assertTrue(any("denies" in item for item in self.validate(req)))

    def test_manual_admission_binds_every_declared_operation_fact(self):
        base = request("R4"); recovery(base)
        self.bind(base, record(base, "full-auto"))
        base["approvals"] = operation(risk="R4")["approvals"]
        bind_approvals(base)
        self.assertEqual(self.validate(base), [])
        for section, field, value in (
            ("target", "owner", "team:other"), ("target", "environment", "production"),
            ("target", "profile_digest", "sha256:"+"f"*64),
            ("change", "scope", ["backup:other"]), ("change", "action", "backup_erasure"),
            ("change", "irreversible", True), ("change", "destructive", True),
            ("change", "stateful", False), ("change", "external_side_effects", False),
            ("execution", "window_end", "2026-08-17T10:45:00Z"),
            ("execution", "executor", "service:other"),
            ("recovery", "method", "another recovery method"),
            ("verification", "criteria", ["different acceptance"]),
        ):
            changed = copy.deepcopy(base); changed[section][field] = value
            self.assertTrue(any("whole operation digest" in reason for reason in self.validate(changed)), (section, field))
        changed = copy.deepcopy(base)
        changed["change"].update(scope=["backup:outside"], destructive=True, irreversible=True)
        self.assertTrue(any("whole operation digest" in reason for reason in self.validate(changed)))
        bind_approvals(changed)  # New separate synthetic admission for the changed operation.
        self.assertEqual(self.validate(changed), [])
        del changed["approvals"][0]["operation_digest"]
        self.assertTrue(self.validate(changed))

    def test_authority_issuers_cover_strictest_class_below_ceiling(self):
        policy = copy.deepcopy(POLICY); policy["minimum_approvals"]["R2"] = 2
        G.validate_policy_shape(policy, "stricter")
        G.ensure_not_weaker(POLICY, policy, "stricter")
        binding = A.digest(policy)
        req = request(); req["policy"]["digest"] = binding
        grant = record(req, "full-auto"); self.bind(req, grant)
        self.assertTrue(any("authorizers" in reason for reason in self.validate(req, policy, binding)))
        authorize(grant, actors=(("user:owner", "service-owner"), ("user:security", "security-owner")))
        self.bind(req, grant)
        self.assertEqual(self.validate(req, policy, binding), [])

    def test_operation_hash_utility_never_issues_admission(self):
        req = request(); path = self.store/"operation.json"
        path.write_text(json.dumps(req), encoding="utf-8")
        result = subprocess.run([sys.executable, str(ROOT/"devops-platform-contracts/scripts/operation_gate.py"),
                                 "--request", str(path), "--print-operation-digest"], capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertIn(G.operation_digest(req), result.stdout)
        self.assertNotIn("ALLOWED:", result.stdout)
        self.assertIn("does not validate or authorize", result.stdout)
        before = G.operation_digest(req)
        req["approvals"] = operation()["approvals"]
        bind_approvals(req)
        self.assertEqual(G.operation_digest(req), before)
        req["change"]["scope"] = ["service:other"]
        self.assertNotEqual(G.operation_digest(req), before)

    def test_manual_issuer_roles_and_executor_casing_cannot_evade_separation(self):
        policy, binding = G.load_registered_policy("enterprise-policy.json")
        req = operation(risk="R4", approvals=2, policy_name="enterprise-policy.json")
        req["execution"]["change_lock_ref"] = "lock:synthetic-target"
        bind_approvals(req)
        self.assertEqual(self.validate(req, policy, binding), [])
        req["approvals"][1]["approver"] = req["approvals"][0]["approver"].upper()
        self.assertTrue(any("distinct valid" in reason for reason in self.validate(req, policy, binding)))
        req["approvals"][1]["approver"] = "user:another-owner"
        req["approvals"][1]["role"] = req["approvals"][0]["role"].upper()
        self.assertTrue(any("distinct approval roles" in reason for reason in self.validate(req, policy, binding)))
        req["approvals"][1].update(approver=req["execution"]["executor"].upper(), role="security-owner")
        self.assertTrue(any("executor cannot approve" in reason for reason in self.validate(req, policy, binding)))

    def test_revocation_during_durable_intent_blocks_child_launch(self):
        wrapper_spec = importlib.util.spec_from_file_location("final_admission_executor", ROOT/"tools/devops_exec.py")
        wrapper = importlib.util.module_from_spec(wrapper_spec); wrapper_spec.loader.exec_module(wrapper)
        marker, path, journal = self.store/"must-not-launch", self.store/"plan.json", self.store/"journal.jsonl"
        argv = [sys.executable, "-c", "from pathlib import Path; Path("+repr(str(marker))+").touch()"]
        req = request(); req["change"]["plan_digest"] = wrapper.canonical_command_digest(argv)
        now = datetime.now(timezone.utc)
        req["execution"].update(window_start=(now-timedelta(minutes=1)).isoformat(), requested_at=now.isoformat(), window_end=(now+timedelta(minutes=10)).isoformat())
        grant = record(req); self.bind(req, grant)
        path.write_text(json.dumps(req), encoding="utf-8")
        append = wrapper.append_ledger
        def revoke_after_intent(destination, entry):
            append(destination, entry)
            if entry["status"] == "launch_intent":
                grant["status"] = "revoked"
                (self.store/(IDENTITY+".json")).write_text(json.dumps(grant), encoding="utf-8")
        with (
            mock.patch.dict(os.environ, {A.AUTHORITY_ENV: str(self.store)}),
            mock.patch.object(wrapper, "append_ledger", side_effect=revoke_after_intent),
            mock.patch.object(sys, "argv", ["devops_exec.py", "--operation", str(path), "--ledger", str(journal), "--", *argv]),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(wrapper.execute(), 3)
        self.assertFalse(marker.exists())
        self.assertEqual([json.loads(line)["status"] for line in journal.read_text().splitlines()], ["launch_intent", "blocked_final_gate"])

    def test_authority_store_is_explicit_external_and_rejects_malformed_files(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(ValueError): A.load_authorization(IDENTITY)
        for path in ("relative-store", ROOT):
            with self.assertRaises(ValueError): A.load_authorization(IDENTITY, path)
        for identifier in ("../authority-escape", "authority-../bad", "C:\\secrets", "unknown"):
            with self.assertRaises(ValueError): A.load_authorization(identifier, self.store)
        path = self.store/(IDENTITY+".json")
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b"x"*65537, b"[]", b"\xff"):
            path.write_bytes(raw)
            with self.assertRaises((ValueError, UnicodeError)): A.load_authorization(IDENTITY, self.store)

    def test_hardlink_authority_is_rejected(self):
        path = self.store/"original.json"; path.write_text("{}", encoding="utf-8")
        linked = self.store/(IDENTITY+".json")
        try: os.link(path, linked)
        except OSError: self.skipTest("hardlinks unavailable")
        with self.assertRaises(ValueError): A.load_authorization(IDENTITY, self.store)

    @unittest.skipUnless(os.name == "posix", "POSIX FIFO")
    def test_fifo_authority_is_rejected_without_blocking(self):
        os.mkfifo(self.store/(IDENTITY+".json"))
        with self.assertRaises(ValueError): A.load_authorization(IDENTITY, self.store)

    def test_wildcards_and_unknown_fields_are_not_broad_grants(self):
        for key, value in (("actions", ["*"]), ("scope", ["namespace:*"]), ("unexpected", True)):
            req = request(); grant = record(req); grant[key] = value
            authorize(grant); self.bind(req, grant)
            self.assertTrue(self.validate(req))
        req = request(); req["change"]["scope"] = ["endpoint:[::1]:8443"]
        self.bind(req, record(req))
        self.assertEqual(self.validate(req), [])

    def test_gate_test_clock_is_rejected_with_configured_authority(self):
        path = self.store/"request.json"; path.write_text(json.dumps(request("R0")), encoding="utf-8")
        env = dict(os.environ, DEVOPS_AUTHORITY_DIR=str(self.store))
        result = subprocess.run([sys.executable, str(ROOT/"devops-platform-contracts/scripts/operation_gate.py"),
                                 "--request", str(path), "--at", NOW.isoformat()], env=env, capture_output=True, text=True, timeout=10)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("test clocks", result.stdout)

    def test_preparer_only_emits_unapproved_draft(self):
        req = request(); path = self.store/"request.json"; path.write_text(json.dumps(req), encoding="utf-8")
        output = self.store/"draft.json"
        env = dict(os.environ); env.pop(A.AUTHORITY_ENV, None)
        result = subprocess.run([sys.executable, str(ROOT/"devops-platform-contracts/scripts/autonomy.py"),
                                 "--draft-from", str(path), "--mode", "balanced", "--authorization-id", IDENTITY,
                                 "--output", str(output)], env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        grant = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(grant["status"], "draft")
        self.assertEqual(grant["authorizations"], [])
        self.bind(req, grant)
        self.assertTrue(self.validate(req))

    def test_two_planned_commands_share_authority_and_revocation_stops_next_launch(self):
        profile = ROOT/"devops-platform-contracts/templates/target-profile.yaml"
        planner = ROOT/"tools/devops_plan.py"; wrapper = ROOT/"tools/devops_exec.py"
        initial = self.store/"initial.json"
        env = dict(os.environ); env.pop(A.AUTHORITY_ENV, None)
        common = ["--target-profile", str(profile), "--action", "build_release", "--risk", "R2",
                  "--objective", "Exercise scoped synthetic release work", "--scope", "service:api",
                  "--verify", "owned fixture marker exists"]
        seed = subprocess.run([sys.executable, str(planner), *common, "--output", str(initial), "--", sys.executable, "-c", "print('seed')"],
                              env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(seed.returncode, 0, seed.stdout+seed.stderr)
        req = json.loads(initial.read_text(encoding="utf-8")); req["change"]["irreversible"] = False
        grant = record(req)
        now = datetime.now(timezone.utc)
        grant["window_start"] = (now-timedelta(minutes=1)).isoformat()
        grant["window_end"] = (now+timedelta(minutes=30)).isoformat()
        authorize(grant)
        authority_path = self.store/(IDENTITY+".json")
        authority_path.write_text(json.dumps(grant), encoding="utf-8")
        env[A.AUTHORITY_ENV] = str(self.store)
        ledger = self.store/"execution.jsonl"
        for index in (1, 2):
            marker = self.store/("marker"+str(index))
            argv = [sys.executable, "-c", "from pathlib import Path; Path("+repr(str(marker))+").write_text('owned')"]
            output = self.store/("plan"+str(index)+".json")
            planned = subprocess.run([sys.executable, str(planner), *common, "--mode", "balanced", "--authorization-id", IDENTITY,
                                      "--output", str(output), "--", *argv], env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(planned.returncode, 0, planned.stdout+planned.stderr)
            candidate = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(candidate["approvals"], [])
            self.assertEqual(A.timestamp(candidate["execution"]["window_end"], "end"), A.timestamp(grant["window_end"], "end"))
            self.assertIn("No additional human confirmation", planned.stderr)
            launched = subprocess.run([sys.executable, str(wrapper), "--operation", str(output), "--ledger", str(ledger),
                                      "--timeout-seconds", "10", "--", *argv], env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(launched.returncode, 0, launched.stdout+launched.stderr)
            self.assertEqual(marker.read_text(encoding="utf-8"), "owned")
        entries = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        self.assertEqual([item["status"] for item in entries], ["launch_intent", "executed"]*2)
        self.assertTrue(all(item["autonomy"]["authorization_id"] == IDENTITY for item in entries))
        blocked_marker = self.store/"must-not-execute"
        argv = [sys.executable, "-c", "from pathlib import Path; Path("+repr(str(blocked_marker))+").touch()"]
        candidate["change"]["plan_digest"] = "sha256:"+__import__("hashlib").sha256(json.dumps(argv, separators=(",", ":")).encode()).hexdigest()
        output.write_text(json.dumps(candidate), encoding="utf-8")
        grant["status"] = "revoked"; authority_path.write_text(json.dumps(grant), encoding="utf-8")
        blocked = subprocess.run([sys.executable, str(wrapper), "--operation", str(output), "--ledger", str(ledger), "--", *argv],
                                 env=env, capture_output=True, text=True, timeout=20)
        self.assertEqual(blocked.returncode, 3, blocked.stdout+blocked.stderr)
        self.assertFalse(blocked_marker.exists())

    def test_executor_gate_receives_frozen_request_despite_path_replacement(self):
        wrapper_spec = importlib.util.spec_from_file_location("frozen_authority_executor", ROOT/"tools/devops_exec.py")
        wrapper = importlib.util.module_from_spec(wrapper_spec); wrapper_spec.loader.exec_module(wrapper)
        marker, path, ledger = self.store/"must-not-execute", self.store/"operation.json", self.store/"journal.jsonl"
        argv = [sys.executable, "-c", "from pathlib import Path; Path("+repr(str(marker))+").touch()"]
        unapproved = operation(approvals=0)
        unapproved["objective"] = "Verify frozen request with Unicode 🎛"
        unapproved["change"]["plan_digest"] = wrapper.canonical_command_digest(argv)
        replacement = operation(approvals=1)
        path.write_text(json.dumps(unapproved), encoding="utf-8")
        original_run = subprocess.run
        calls = []
        def replace_before_gate(command, **kwargs):
            path.write_text(json.dumps(replacement), encoding="utf-8")
            calls.append((command, kwargs))
            return original_run(command, **kwargs)
        with (
            mock.patch.dict(os.environ, {A.AUTHORITY_ENV: ""}),
            mock.patch.object(sys, "argv", ["devops_exec.py", "--operation", str(path), "--ledger", str(ledger), "--at", NOW.isoformat(), "--", *argv]),
            mock.patch.object(wrapper.subprocess, "run", side_effect=replace_before_gate),
            redirect_stdout(io.StringIO()),
        ):
            self.assertEqual(wrapper.execute(), 3)
        self.assertFalse(marker.exists())
        self.assertEqual(len(calls), 1)
        self.assertIn("--request-stdin", calls[0][0])
        self.assertEqual(json.loads(calls[0][1]["input"]), unapproved)
        self.assertTrue(all(ord(character) < 128 for character in calls[0][1]["input"]))

    def test_executor_rejects_ambiguous_oversized_and_nonregular_requests(self):
        wrapper_spec = importlib.util.spec_from_file_location("strict_operation_executor", ROOT/"tools/devops_exec.py")
        wrapper = importlib.util.module_from_spec(wrapper_spec); wrapper_spec.loader.exec_module(wrapper)
        path = self.store/"request.json"
        for raw in (b'{"x":1,"x":2}', b'{"x":NaN}', b"x"*1048577):
            path.write_bytes(raw)
            with self.assertRaises(ValueError): wrapper.read_operation(path)
        with self.assertRaises(ValueError): wrapper.read_operation(self.store)

    def test_packagers_reject_issued_private_authority_records(self):
        for name, source in (("release", "tools/build_release.py"), ("public", "tools/build_public_source.py")):
            spec = importlib.util.spec_from_file_location("authority_"+name, ROOT/source)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            fixture = self.store/name; fixture.mkdir()
            path = fixture/"private.json"
            path.write_text(json.dumps(record(request())), encoding="utf-8")
            module.ROOT = fixture
            if name == "release":
                with self.assertRaisesRegex(ValueError, "private autonomy"): module.safe_read(path)
            else:
                # Exercise actual export main after isolated metadata validation.
                module.public_files = lambda catalog: [path]
                (fixture/"catalog.json").write_text(json.dumps({"name": "fixture", "version": "0.9.0"}), encoding="utf-8")
                output = self.store/"must-not-export"
                with (
                    mock.patch.object(sys, "argv", ["build_public_source.py", "--output", str(output)]),
                    mock.patch.object(module.subprocess, "run", return_value=type("Result", (), {"returncode": 0})()),
                    redirect_stdout(captured := io.StringIO()),
                ):
                    self.assertEqual(module.main(), 1)
                self.assertIn("private autonomy", captured.getvalue())
                self.assertFalse(output.exists())
