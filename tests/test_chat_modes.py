from __future__ import annotations

import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT.parent


def digest(value):
    return "sha256:"+hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


class ChatModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix="chat-mode-tests-", dir=WORK)
        cls.base = Path(cls.temporary.name)
        assert cls.base.resolve().is_relative_to(WORK.resolve())
        cls.snapshot = cls.base/"snapshot"
        result = subprocess.run([sys.executable, str(ROOT/"tools/install.py"), "--runtime", "--destination", str(cls.snapshot), "--apply"],
                                capture_output=True, text=True, timeout=30)
        if result.returncode: raise RuntimeError(result.stdout+result.stderr)

    @classmethod
    def tearDownClass(cls): cls.temporary.cleanup()

    def setUp(self):
        self.case = self.base/("case-"+__import__("uuid").uuid4().hex[:8])
        self.runtime = self.case/"runtime"; shutil.copytree(self.snapshot, self.runtime)
        self.workspace = self.case/"project"; self.workspace.mkdir()
        self.codex_home = self.case/"codex-home"
        self.sid = "synthetic-chat-001"
        self.env = dict(os.environ, CODEX_THREAD_ID=self.sid, CODEX_SESSION_ID=self.sid, PYTHONUTF8="1", PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("DEVOPS_AUTHORITY_DIR", None)
        self.profile = self.runtime/"devops-platform-contracts/templates/target-profile.yaml"
        key = hashlib.sha256(os.path.normcase(str(self.runtime.resolve())).encode()).hexdigest()
        self.state = self.runtime.parent/".devops-skill-state"/key[:16]

    def cli(self, script, *args, env=None, cwd=None, input=None):
        return subprocess.run([sys.executable, str(self.runtime/script), *map(str, args)], env=env or self.env,
                              cwd=cwd or self.workspace, input=input, capture_output=True, text=True, timeout=30)

    def setup(self, policy=None):
        args = ["setup", "--codex-home", self.codex_home, "--apply"]
        if policy: args += ["--policy", policy]
        result = self.cli("tools/devops_mode.py", *args)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.hook(kind="SessionStart")  # Synthetic host readiness, never inferred from setup itself.
        return result

    def prepare(self, mode="balanced", extra=(), setup=True):
        if setup: self.setup()
        result = self.cli("tools/devops_mode.py", "prepare", "--mode", mode, "--target-profile", self.profile,
                          "--action", "build_release", "--scope", "service:api", *extra)
        return result

    def pending_path(self, sid=None):
        return self.runtime/"operations/chat-modes"/hashlib.sha256((sid or self.sid).encode()).hexdigest()[:20]/"pending.json"

    def pending(self): return json.loads(self.pending_path().read_text(encoding="utf-8"))

    def selection_path(self, sid=None):
        return self.state/"sessions"/(hashlib.sha256((sid or self.sid).encode()).hexdigest()[:20]+".json")

    def selected(self): return json.loads(self.selection_path().read_text(encoding="utf-8"))

    def hook(self, prompt=None, sid=None, cwd=None, kind="UserPromptSubmit"):
        event = {"session_id": sid or self.sid, "cwd": str(cwd or self.workspace), "hook_event_name": kind,
                 "turn_id": "synthetic-turn-001", "permission_mode": "default", "prompt": prompt or "ordinary user task"}
        result = self.cli("tools/hooks/chat_mode_hook.py", input=json.dumps(event), cwd=cwd)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        return result

    def confirm(self): return self.hook("Подтверждаю границы "+digest(self.pending())[7:23])

    def grant(self):
        return self.state/"authorities"/(self.selected()["selection"]["authorization_id"]+".json")

    def plan(self, index=1, env=None, risk="R2", extra=()):
        marker = self.workspace/("marker-"+str(index))
        argv = [sys.executable, "-c", "from pathlib import Path; Path("+repr(str(marker))+").write_text('owned')"]
        path = self.workspace/("operation-"+str(index)+".json")
        result = self.cli("tools/devops_plan.py", "--action", "build_release", "--risk", risk,
                          "--objective", "Exercise bounded synthetic chat work", "--scope", "service:api",
                          "--verify", "owned marker exists", "--output", path, *extra, "--", *argv, env=env)
        return result, path, marker, argv

    def execute(self, path, argv, env=None, cwd=None):
        return self.cli("tools/devops_exec.py", "--operation", path, "--ledger", self.workspace/"ledger.jsonl", "--", *argv, env=env, cwd=cwd)

    def test_remote_safe_also_restricts_local_planning_without_second_remote_call(self):
        self.prepare(); self.confirm()
        (self.runtime/'broker-client.json').write_text('{}',encoding='utf-8')
        spec=importlib.util.spec_from_file_location('chat_safe_remote_fixture',self.runtime/'tools/hooks/chat_mode_hook.py')
        hook=importlib.util.module_from_spec(spec); spec.loader.exec_module(hook)
        client=mock.Mock(); client.call_broker.return_value={'status':'restricted','mode':'safe'}
        original=hook.chat.module
        def module(name,path):
            return client if name=='host_broker_restriction_client' else original(name,path)
        event={'hook_event_name':'UserPromptSubmit','prompt':'Safe','session_id':self.sid,'cwd':str(self.workspace)}
        from types import SimpleNamespace
        with mock.patch.dict(os.environ,self.env),mock.patch.object(hook.chat,'module',side_effect=module),mock.patch('sys.stdin',SimpleNamespace(buffer=io.BytesIO(json.dumps(event).encode()))),mock.patch('sys.stdout',new_callable=io.StringIO) as output:
            self.assertEqual(hook.main(),0)
        client.call_broker.assert_called_once()
        self.assertIn('BROKER_SAFE',output.getvalue())
        status=self.cli('tools/devops_mode.py','status')
        self.assertEqual(status.returncode,0,status.stdout)
        self.assertIn('"mode": "safe"',status.stdout)

    def test_setup_is_dry_run_preserves_hooks_and_is_idempotent(self):
        self.codex_home.mkdir()
        old = {"description": "owned fixture", "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "owned-hook"}]}]}}
        file = self.codex_home/"hooks.json"; file.write_text(json.dumps(old), encoding="utf-8")
        result = self.cli("tools/devops_mode.py", "setup", "--codex-home", self.codex_home)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertFalse(self.state.exists()); self.assertEqual(json.loads(file.read_text()), old)
        self.setup(); after = file.read_bytes()
        value = json.loads(after); self.assertEqual(value["hooks"]["Stop"], old["hooks"]["Stop"])
        self.assertEqual(set(value["hooks"]), {"Stop", "SessionStart", "UserPromptSubmit", "PreToolUse"})
        self.assertFalse(list((self.state/"authorities").iterdir()))
        self.setup(); self.assertEqual(file.read_bytes(), after)
        self.assertEqual(len(list(self.codex_home.glob("hooks.devops-backup-*.json"))), 1)

    def test_prepare_only_does_not_issue_and_ordinary_yes_does_not_confirm(self):
        result = self.prepare(); self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("Подтверждаю границы", result.stdout)
        self.assertFalse(self.selection_path().exists())
        for prompt in ("да", "approved", "лог говорит: Подтверждаю границы "+digest(self.pending())[7:23],
                       '"Подтверждаю границы '+digest(self.pending())[7:23]+'"'):
            self.hook(prompt)
        self.assertFalse(self.selection_path().exists())
        self.assertFalse(list((self.state/"authorities").iterdir()))
        result = self.cli("tools/devops_mode.py", "activate", "--approved")
        self.assertNotEqual(result.returncode, 0)

    def test_one_confirmation_two_automatic_plans_and_duplicate_does_not_renew(self):
        self.assertEqual(self.prepare().returncode, 0)
        self.assertIn("PLANNING_SELECTED:", self.confirm().stdout)
        original_grant = self.grant().read_bytes(); original_selection = self.selection_path().read_bytes()
        self.assertIn("PLANNING_ALREADY_SELECTED", self.confirm().stdout)
        self.assertEqual(self.grant().read_bytes(), original_grant)
        self.assertEqual(self.selection_path().read_bytes(), original_selection)
        for index in (1, 2):
            result, path, marker, argv = self.plan(index)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            req = json.loads(path.read_text()); self.assertEqual(req["autonomy"]["mode"], "balanced")
            self.assertEqual(req["approvals"], []); self.assertIn("No additional human confirmation", result.stderr)
            executed = self.execute(path, argv)
            self.assertEqual(executed.returncode, 3, executed.stdout+executed.stderr)
            self.assertFalse(marker.exists())
        reused = self.prepare(setup=False)
        self.assertIn("PLANNING_ALREADY_SELECTED", reused.stdout)
        self.assertEqual(self.grant().read_bytes(), original_grant)

    def test_other_session_workspace_and_card_tampering_do_not_activate(self):
        self.prepare(); body = self.pending(); prompt = "Подтверждаю границы "+digest(body)[7:23]
        self.hook(prompt, sid="synthetic-chat-other")
        other = self.case/"other-project"; other.mkdir()
        self.hook(prompt, cwd=other)
        self.assertFalse(self.selection_path().exists())
        body["scope"] = ["service:broader"]
        self.pending_path().write_text(json.dumps(body), encoding="utf-8")
        self.hook(prompt)
        self.assertFalse(self.selection_path().exists())

    def test_profile_policy_and_expired_card_stop_confirmation(self):
        for mutation in ("profile", "policy", "expired"):
            with self.subTest(mutation=mutation):
                self.prepare(); body = self.pending(); prompt = "Подтверждаю границы "+digest(body)[7:23]
                if mutation == "profile":
                    raw = self.profile.read_bytes(); self.profile.write_bytes(raw.replace(b"example-lab", b"changed-lab"))
                elif mutation == "policy":
                    file = self.runtime/"devops-platform-contracts/policies/default-policy.json"
                    raw = file.read_bytes(); value = json.loads(raw); value["approval_ttl_minutes"] = 121
                    file.write_text(json.dumps(value), encoding="utf-8")
                else:
                    body["confirm_before"] = "2020-01-01T00:00:00Z"
                    self.pending_path().write_text(json.dumps(body), encoding="utf-8")
                    prompt = "Подтверждаю границы "+digest(body)[7:23]
                self.hook(prompt); self.assertFalse(self.selection_path().exists())
                if mutation == "profile": self.profile.write_bytes(raw)
                if mutation == "policy": file.write_bytes(raw)

    def test_safe_and_revoke_block_previously_prepared_plans(self):
        self.prepare(); self.confirm(); old_prompt = "Подтверждаю границы "+digest(self.pending())[7:23]
        result, path, marker, argv = self.plan()
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        grant_path = self.grant()
        self.hook("работай в Safe")
        self.assertEqual(json.loads(grant_path.read_text())["status"], "revoked")
        self.assertEqual(self.selected()["selection"]["mode"], "safe")
        result = self.execute(path, argv)
        self.assertEqual(result.returncode, 3, result.stdout); self.assertFalse(marker.exists())
        self.hook(old_prompt)
        self.assertEqual(self.selected()["selection"]["mode"], "safe")

    def test_agent_safe_latch_only_restricts_until_new_host_confirmation(self):
        self.prepare(); self.confirm()
        result, path, marker, argv = self.plan()
        self.assertEqual(result.returncode, 0, result.stdout)
        result = self.cli("tools/devops_mode.py", "safe")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.execute(path, argv).returncode, 3); self.assertFalse(marker.exists())
        self.prepare(setup=False); self.assertIn("PLANNING_SELECTED:", self.confirm().stdout)
        result, path, marker, argv = self.plan(2)
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual(self.execute(path, argv).returncode, 3)

    def test_scope_and_ceiling_still_need_exact_admission(self):
        self.prepare(); self.confirm()
        for index, extra, risk in ((1, ["--scope", "service:other"], "R2"), (2, [], "R3"), (3, ["--irreversible"], "R4")):
            result, path, marker, argv = self.plan(index, risk=risk, extra=extra)
            self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
            req = json.loads(path.read_text()); self.assertTrue(req["approvals"])
            self.assertEqual(self.execute(path, argv).returncode, 3); self.assertFalse(marker.exists())

    def test_cross_session_explicit_mode_and_expired_authority_never_fall_back(self):
        self.prepare(); self.confirm()
        result, path, marker, argv = self.plan()
        self.assertEqual(result.returncode, 0, result.stdout)
        env = dict(self.env, CODEX_THREAD_ID="synthetic-other-session", CODEX_SESSION_ID="synthetic-other-session")
        self.assertEqual(self.execute(path, argv, env=env).returncode, 3); self.assertFalse(marker.exists())
        result, _, _, _ = self.plan(2, extra=["--mode", "full-auto"])
        self.assertNotEqual(result.returncode, 0)
        record = json.loads(self.grant().read_text()); record["window_end"] = "2020-01-01T00:00:00Z"
        self.grant().write_text(json.dumps(record), encoding="utf-8")
        result, _, _, _ = self.plan(3)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.execute(path, argv).returncode, 3)

    def test_enterprise_cap_no_policy_substitution_or_fake_second_owner(self):
        self.setup("enterprise-policy.json")
        result = self.prepare(setup=False)
        self.assertNotEqual(result.returncode, 0)
        result = self.prepare(extra=["--policy", "default-policy.json"], setup=False)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse(list((self.state/"authorities").iterdir()))

    def test_semi_and_full_auto_require_their_existing_safeguards(self):
        self.assertEqual(self.prepare("semi-auto").returncode, 0)
        self.assertIn("PLANNING_SELECTED:", self.confirm().stdout)
        result, path, marker, argv = self.plan(risk="R3")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.execute(path, argv).returncode, 3)  # Missing target lock.
        self.hook("Safe")
        self.assertNotEqual(self.prepare("full-auto", setup=False).returncode, 0)
        result = self.prepare("full-auto", extra=["--isolation-ref", "fixture:isolated-lab", "--credential-scope-ref", "fixture:bounded-role", "--owner-evidence-ref", "fixture:owner-review"], setup=False)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("fixture:isolated-lab", result.stdout)
        self.assertIn("PLANNING_SELECTED:", self.confirm().stdout)

    def test_malformed_host_input_cannot_issue_or_leak_raw_event(self):
        self.setup()
        for raw in ('{"prompt":"SENSITIVE-FIXTURE","prompt":"duplicate"}', '{"value":NaN}', '[]', 'x'*65537):
            result = self.cli("tools/hooks/chat_mode_hook.py", input=raw)
            self.assertEqual(result.returncode, 0)
            self.assertNotIn("SENSITIVE-FIXTURE", result.stdout+result.stderr)
            self.assertFalse(list((self.state/"authorities").iterdir()))

    def test_workspace_move_requires_new_card_and_confirmation(self):
        self.prepare(); self.confirm()
        other = self.case/"new-project"; other.mkdir()
        result = self.cli("tools/devops_mode.py", "prepare", "--mode", "balanced", "--target-profile", self.profile,
                          "--action", "build_release", "--scope", "service:api", cwd=other)
        self.assertEqual(result.returncode, 0, result.stdout)
        prompt = "Подтверждаю границы "+digest(self.pending())[7:23]
        self.assertIn("PLANNING_SELECTED:", self.hook(prompt, cwd=other).stdout)
        self.assertEqual(self.selected()["workspace"], str(other.resolve()))

    def test_no_clock_override_in_registered_chat_runtime(self):
        self.prepare(); self.confirm()
        result, _, _, _ = self.plan(extra=["--at", "2026-08-17T10:00:00Z"])
        self.assertNotEqual(result.returncode, 0)

    def test_setup_rejects_hook_symlinks_without_touching_target(self):
        self.codex_home.mkdir()
        target = self.case/"keep.json"; target.write_text('{"hooks":{}}', encoding="utf-8")
        try: (self.codex_home/"hooks.json").symlink_to(target)
        except OSError: self.skipTest("symlinks unavailable")
        result = self.cli("tools/devops_mode.py", "setup", "--codex-home", self.codex_home, "--apply")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(target.read_text(), '{"hooks":{}}')

    def test_setup_alone_does_not_claim_a_trusted_or_observed_hook(self):
        result = self.cli("tools/devops_mode.py", "setup", "--codex-home", self.codex_home, "--apply")
        self.assertEqual(result.returncode, 0, result.stdout)
        result = self.cli("tools/devops_mode.py", "status")
        self.assertIn("HOST_HOOK_NOT_OBSERVED", result.stdout)
        self.assertFalse(self.selection_path().exists())
        self.hook(kind="SessionStart")
        self.assertIn("SAFE:", self.cli("tools/devops_mode.py", "status").stdout)

    def test_setup_respects_existing_codex_home_without_manual_path_flags(self):
        env = dict(self.env, CODEX_HOME=str(self.codex_home))
        result = self.cli("tools/devops_mode.py", "setup", "--apply", env=env)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertTrue((self.codex_home/"hooks.json").is_file())

    def test_confirmation_requires_actual_host_event_identity_fields(self):
        self.prepare(); prompt = "Подтверждаю границы "+digest(self.pending())[7:23]
        base = {"session_id": self.sid, "cwd": str(self.workspace), "hook_event_name": "UserPromptSubmit", "turn_id": "synthetic-turn", "prompt": prompt}
        for key in ("session_id", "cwd", "turn_id"):
            event = dict(base); del event[key]
            self.cli("tools/hooks/chat_mode_hook.py", input=json.dumps(event))
            self.assertFalse(self.selection_path().exists(), key)

    def test_pending_retry_does_not_replace_the_displayed_confirmation(self):
        self.prepare(); original = self.pending_path().read_bytes()
        retry = self.prepare(setup=False)
        self.assertEqual(retry.returncode, 0, retry.stdout)
        self.assertEqual(self.pending_path().read_bytes(), original)
        self.assertIn(digest(self.pending())[7:23], retry.stdout)

    def test_two_chats_same_workspace_have_separate_selection_and_revocation(self):
        self.prepare(); self.confirm(); first_grant = self.grant()
        other = "synthetic-chat-002"
        env = dict(self.env, CODEX_THREAD_ID=other, CODEX_SESSION_ID=other)
        result = self.cli("tools/devops_mode.py", "prepare", "--mode", "balanced", "--target-profile", self.profile,
                          "--action", "build_release", "--scope", "service:api", env=env)
        self.assertEqual(result.returncode, 0, result.stdout)
        body = json.loads(self.pending_path(other).read_text())
        self.assertIn("PLANNING_SELECTED:", self.hook("Подтверждаю границы "+digest(body)[7:23], sid=other).stdout)
        second = json.loads(self.selection_path(other).read_text())
        self.assertNotEqual(self.selected()["selection"]["authorization_id"], second["selection"]["authorization_id"])
        self.hook("Safe", sid=other)
        self.assertEqual(json.loads(first_grant.read_text())["status"], "active")
        result, path, _, argv = self.plan()
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual(self.execute(path, argv).returncode, 3)

    def test_interrupted_publication_recovers_without_renewal_or_orphan_admission(self):
        self.prepare()
        spec = importlib.util.spec_from_file_location("synthetic_chat_crash", self.runtime/"devops-platform-contracts/scripts/chat_modes.py")
        chat = importlib.util.module_from_spec(spec); spec.loader.exec_module(chat)
        write = chat.atomic_write
        def fail_selection(path, value):
            if path == chat.selection_path(self.sid): raise OSError("synthetic publication interruption")
            return write(path, value)
        event = {"session_id": self.sid, "cwd": str(self.workspace), "hook_event_name": "UserPromptSubmit",
                 "turn_id": "synthetic-turn-001", "prompt": "Подтверждаю границы "+digest(self.pending())[7:23]}
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(chat, "atomic_write", side_effect=fail_selection):
            with self.assertRaises(OSError): chat.host_event(event)
        self.assertFalse(self.selection_path().exists())
        records = list((self.state/"authorities").glob("*.json")); self.assertEqual(len(records), 1)
        original = records[0].read_bytes()
        orphan = json.loads(original)
        result, path, marker, argv = self.plan(extra=["--target-profile", str(self.profile), "--mode", "balanced", "--authorization-id", orphan["authorization_id"]])
        self.assertNotEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertFalse(marker.exists())
        self.assertIn("PLANNING_SELECTED:", self.confirm().stdout)
        self.assertEqual(records[0].read_bytes(), original)

    def test_unknown_card_fields_and_post_activation_profile_drift_block(self):
        self.prepare(); body = self.pending(); body["extra_authority"] = True
        self.pending_path().write_text(json.dumps(body), encoding="utf-8")
        self.confirm(); self.assertFalse(self.selection_path().exists())
        self.pending_path().unlink()
        self.prepare(setup=False); self.confirm()
        result, path, marker, argv = self.plan()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.profile.write_bytes(self.profile.read_bytes().replace(b"example-lab", b"changed-lab"))
        self.assertEqual(self.execute(path, argv).returncode, 3); self.assertFalse(marker.exists())
        self.assertNotEqual(self.cli("tools/devops_mode.py", "status").returncode, 0)
        self.assertNotIn("PLANNING_ALREADY_SELECTED", self.confirm().stdout)

    def test_concurrent_same_confirmation_issues_once_with_fixed_expiry(self):
        from concurrent.futures import ThreadPoolExecutor
        self.prepare(); body = self.pending(); prompt = "Подтверждаю границы "+digest(body)[7:23]
        with ThreadPoolExecutor(max_workers=3) as pool:
            outputs = list(pool.map(lambda _: self.hook(prompt).stdout, range(3)))
        self.assertTrue(any("PLANNING_SELECTED:" in output for output in outputs))
        self.assertEqual(len(list((self.state/"authorities").glob("*.json"))), 1)
        self.assertEqual(json.loads(self.grant().read_text())["window_end"], body["window_end"])

    def test_safe_under_issuer_lock_contention_blocks_old_plan_immediately(self):
        self.prepare(); self.confirm()
        result, path, marker, argv = self.plan()
        self.assertEqual(result.returncode, 0, result.stdout)
        spec = importlib.util.spec_from_file_location("synthetic_contention_chat", self.runtime/"devops-platform-contracts/scripts/chat_modes.py")
        chat = importlib.util.module_from_spec(spec); spec.loader.exec_module(chat)
        support = chat.module("synthetic_contention_lock", self.runtime/"tools/runtime_lock.py")
        with support.runtime_lock(self.runtime.parent/(".chat-coordination-"+chat.runtime_id()[:16])):
            self.assertIn("SAFE:", self.hook("Safe").stdout)
            self.assertEqual(self.execute(path, argv).returncode, 3)
        self.assertFalse(marker.exists())

    def test_safe_restriction_applies_before_any_selection_or_chat_setup(self):
        result = self.cli("tools/devops_mode.py", "safe")
        self.assertEqual(result.returncode, 0, result.stdout)
        result, _, marker, _ = self.plan(extra=["--target-profile", str(self.profile), "--mode", "balanced", "--authorization-id", "authority-unselected-example"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("change mode through confirmed chat boundaries", result.stdout)
        self.assertFalse(marker.exists())
        result, path, marker, argv = self.plan(2, extra=["--target-profile", str(self.profile)])
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual(json.loads(path.read_text())["autonomy"]["mode"], "safe")
        self.assertEqual(self.execute(path, argv).returncode, 3); self.assertFalse(marker.exists())

    def test_runtime_replacement_cannot_roll_back_a_new_safe_restriction(self):
        self.prepare(); self.confirm()
        result, path, marker, argv = self.plan()
        self.assertEqual(result.returncode, 0, result.stdout)
        spec = importlib.util.spec_from_file_location("synthetic_upgrade_installer", self.snapshot/"tools/install.py")
        installer = importlib.util.module_from_spec(spec); spec.loader.exec_module(installer)
        original = installer.tree_digest
        destination_reads = []
        def safe_after_final_destination_snapshot(folder):
            value = original(folder)
            if Path(folder) == self.runtime:
                destination_reads.append(1)
                if len(destination_reads) == 2:
                    cancelled = self.cli("tools/devops_mode.py", "safe")
                    self.assertEqual(cancelled.returncode, 0, cancelled.stdout)
            return value
        import argparse
        args = argparse.Namespace(destination=self.runtime, profile=None, force=True, apply=True)
        with mock.patch.object(installer, "tree_digest", side_effect=safe_after_final_destination_snapshot):
            self.assertEqual(installer.install_runtime(args), 0)
        self.assertGreaterEqual(len(destination_reads), 2)
        self.assertEqual(self.execute(path, argv).returncode, 3); self.assertFalse(marker.exists())
        self.prepare(setup=False); self.assertIn("PLANNING_SELECTED:", self.confirm().stdout)
        result, path, marker, argv = self.plan(2)
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertEqual(self.execute(path, argv).returncode, 3)

    def test_new_safe_after_selection_publication_wins_without_deleting_epoch(self):
        self.prepare()
        spec = importlib.util.spec_from_file_location("synthetic_safe_race_chat", self.runtime/"devops-platform-contracts/scripts/chat_modes.py")
        chat = importlib.util.module_from_spec(spec); spec.loader.exec_module(chat)
        write = chat.atomic_write
        def cancel_after_publication(path, value):
            write(path, value)
            if path == chat.selection_path(self.sid):
                cancelled = self.cli("tools/devops_mode.py", "safe")
                self.assertEqual(cancelled.returncode, 0, cancelled.stdout)
        event = {"session_id": self.sid, "cwd": str(self.workspace), "hook_event_name": "UserPromptSubmit",
                 "turn_id": "synthetic-race-turn", "prompt": "Подтверждаю границы "+digest(self.pending())[7:23]}
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(chat, "atomic_write", side_effect=cancel_after_publication):
            self.assertIn("SAFE:", chat.host_event(event))
        self.assertTrue(chat.latch_path(self.sid).is_file())
        result, path, marker, argv = self.plan()
        self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
        self.assertEqual(json.loads(path.read_text())["autonomy"]["mode"], "safe")
        self.assertEqual(self.execute(path, argv).returncode, 3); self.assertFalse(marker.exists())
        self.confirm()  # Original code cannot clear the newer Safe generation.
        self.assertIn('"mode": "safe"', self.cli("tools/devops_mode.py", "status").stdout)

    def test_serialized_hook_command_handles_shell_metacharacters_and_unicode(self):
        moved = self.case/"runtime & shell 'quoted'"
        self.runtime.rename(moved); self.runtime = moved
        self.profile = moved/"devops-platform-contracts/templates/target-profile.yaml"
        key = hashlib.sha256(os.path.normcase(str(self.runtime.resolve())).encode()).hexdigest()
        self.state = self.runtime.parent/".devops-skill-state"/key[:16]
        self.workspace = self.case/"рабочая область"; self.workspace.mkdir()
        interpreter = sys.executable
        if os.name == "nt":
            venv = self.case/"Python & With Spaces"
            made = subprocess.run([sys.executable, "-m", "venv", "--without-pip", "--system-site-packages", str(venv)], capture_output=True, text=True, timeout=30)
            self.assertEqual(made.returncode, 0, made.stdout+made.stderr)
            interpreter = str(venv/"Scripts/python.exe")
        setup = subprocess.run([interpreter, str(self.runtime/"tools/devops_mode.py"), "setup", "--codex-home", str(self.codex_home), "--apply"],
                               env=self.env, cwd=self.workspace, capture_output=True, text=True, timeout=30)
        self.assertEqual(setup.returncode, 0, setup.stdout+setup.stderr)
        command = json.loads((self.codex_home/"hooks.json").read_text())["hooks"]["SessionStart"][0]["hooks"][0]["command"]
        event = json.dumps({"session_id": self.sid, "cwd": str(self.workspace), "hook_event_name": "SessionStart"}, ensure_ascii=False)
        invoked = subprocess.run(command, shell=True, input=event, env=self.env, cwd=self.workspace, capture_output=True, text=True, timeout=30)
        self.assertEqual(invoked.returncode, 0, invoked.stdout+invoked.stderr)
        self.assertEqual(json.loads(invoked.stdout)["hookSpecificOutput"]["hookEventName"], "SessionStart")
        if os.name == "nt":
            invoked = subprocess.run(["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", command], input=event,
                                     env=self.env, cwd=self.workspace, capture_output=True, text=True, timeout=30)
            self.assertEqual(invoked.returncode, 0, invoked.stdout+invoked.stderr)
            self.assertEqual(json.loads(invoked.stdout)["hookSpecificOutput"]["hookEventName"], "SessionStart")
