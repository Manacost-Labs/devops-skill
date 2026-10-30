"""Cryptographic/semantic regression controls; native isolation is separate CI."""
import base64
import copy
from datetime import datetime, timedelta, timezone
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from broker_fixture import C, ROOT, SUBJECT, EPOCH, registry, grant, call, admission, signed


class BrokerContractTests(unittest.TestCase):
    def setUp(self):
        self.registry, self.keys = registry()
        self.grant = grant(self.registry, self.keys)
        self.now = datetime.now(timezone.utc)

    def assess(self, request=None, authority=None, exact=None, **kwargs):
        return C.assess(request or call(), authority or self.grant, exact, self.registry, self.now, SUBJECT, kwargs.pop("epoch", EPOCH), **kwargs)

    def test_legitimate_typed_calls_reuse_one_grant_without_exact_confirmations(self):
        for number in (1, 2):
            result = self.assess(call(operation="ops-fixture-" + str(number)))
            self.assertFalse(result["exact_required"])
            self.assertEqual(result["request"]["change"]["risk"], "R2")
            self.assertEqual(result["signer_ids"], ["owner-key"])

    def test_caller_cannot_supply_risk_argv_target_effects_or_approval_labels(self):
        for field, value in (("risk", "R0"), ("argv", ["python", "-c", "write()"]), ("target", "other"), ("scope", ["all"]), ("destructive", False), ("approvals", [{"approver": "user:invented"}]), ("env", {"DEVOPS_AUTHORITY_DIR": "/fake"})):
            request = call(); request[field] = value
            with self.subTest(field=field), self.assertRaises(C.Denied):
                self.assess(request)

    def test_unknown_tasks_and_unregistered_parameters_are_denied(self):
        for request in (call("unknown-task"), call(parameters={"value": "after", "command": "write()"}), call(parameters={"value": "../../private"}), call(parameters={"value": {"argv": ["sh"]}})):
            with self.subTest(request=request), self.assertRaises(C.Denied):
                self.assess(request)

    def test_forged_signature_and_forged_exact_json_never_authorize(self):
        forged = copy.deepcopy(self.grant)
        forged["signatures"][0]["signature"] = base64.b64encode(b"x" * 64).decode()
        with self.assertRaises(C.Denied):
            self.assess(authority=forged)
        request = call("production-task")
        with self.assertRaises(C.Denied):
            self.assess(request, exact={"approver": "user:invented", "role": "service-owner", "evidence_ref": "ticket:invented"})

    def test_all_four_ceilings_and_separate_destructive_admission(self):
        for mode, level in C.MODES.items():
            authority = grant(self.registry, self.keys, mode=mode)
            for task_id, risk in (("inspect-task", 0), ("configure-task", 2), ("production-task", 3)):
                request = call(task_id)
                if risk <= level:
                    self.assess(request, authority)
                else:
                    with self.assertRaises((C.Denied, TypeError)):
                        self.assess(request, authority)
                    self.assess(request, authority, admission(self.registry, self.keys, request, authority))
        authority = grant(self.registry, self.keys, mode="full-auto")
        request = call("destructive-task")
        with self.assertRaises(C.Denied):
            self.assess(request, authority)
        self.assertTrue(self.assess(request, authority, admission(self.registry, self.keys, request, authority))["exact_required"])

    def test_authentication_is_bound_to_client_server_registry_parameters_and_epoch(self):
        for field, value in (("subject", "sha256:" + "d" * 64), ("audience", "other-broker"), ("registry_digest", "sha256:" + "d" * 64), ("epoch", "d" * 64)):
            payload = copy.deepcopy(self.grant); payload[field] = value
            candidate = signed(payload, self.keys)
            with self.subTest(field=field), self.assertRaises(C.Denied):
                self.assess(authority=candidate)
        request = call("production-task")
        exact = admission(self.registry, self.keys, request, self.grant)
        request["operation_id"] = "ops-fixture-other"
        with self.assertRaises(C.Denied):
            self.assess(request, exact=exact)

    def test_revocation_epoch_restricts_every_overlapping_old_grant(self):
        for authority in (self.grant, grant(self.registry, self.keys, identifier="grant-fixture-two")):
            with self.assertRaises(C.Denied):
                self.assess(authority=authority, epoch="e" * 64, ceiling="safe")
            self.assess(call("inspect-task"), authority=authority, epoch="e" * 64, ceiling="safe")
        renewed = grant(self.registry, self.keys, epoch="e" * 64)
        self.assess(authority=renewed, epoch="e" * 64, ceiling="safe")

    def test_ambient_store_session_and_test_clock_cannot_choose_broker_authority(self):
        with mock.patch.dict(os.environ, {"DEVOPS_AUTHORITY_DIR": "/invented", "CODEX_THREAD_ID": "forged-session", "CODEX_SESSION_ID": "forged-session"}):
            self.assess()
        expired = grant(self.registry, self.keys, start=self.now - timedelta(hours=1), end=self.now - timedelta(seconds=1))
        with self.assertRaises(C.Denied):
            self.assess(authority=expired)
        payload = copy.deepcopy(self.grant); payload["expires"] = (self.now + timedelta(days=30)).isoformat()
        with self.assertRaises(C.Denied):
            self.assess(authority=signed(payload, self.keys))

    def test_duplicate_key_aliases_and_same_actor_cannot_satisfy_separation(self):
        for change in (lambda r: r["keys"].update({"alias-key": dict(r["keys"]["owner-key"])}), lambda r: r["keys"]["security-key"].update(actor=r["keys"]["owner-key"]["actor"])):
            candidate = copy.deepcopy(self.registry); change(candidate)
            with self.assertRaises(C.Denied):
                C.validate_registry(candidate)
        duplicate = copy.deepcopy(self.grant); duplicate["signatures"] *= 2
        with self.assertRaises(C.Denied):
            self.assess(authority=duplicate)

    def test_policy_floor_and_enterprise_signers_are_enforced(self):
        self.registry["targets"]["fixture-target"]["environment"] = "production"
        authority = grant(self.registry, self.keys)
        with self.assertRaises(C.Denied):
            self.assess(call(), authority)
        self.registry["policy"] = "enterprise-policy.json"
        self.registry["policy_digest"] = C.GATE.load_registered_policy("enterprise-policy.json")[1]
        authority = grant(self.registry, self.keys, mode="safe")
        request = call("production-task")
        exact = admission(self.registry, self.keys, request, authority)
        with self.assertRaises(C.Denied):
            self.assess(request, authority, exact)
        exact = admission(self.registry, self.keys, request, authority, selected=("owner-key", "security-key"))
        self.assess(request, authority, exact)

    def test_registry_input_drift_and_duplicate_json_fail_closed(self):
        self.registry["tasks"]["configure-task"]["bundle"]["handler.py"] = "sha256:" + "f" * 64
        with self.assertRaises(C.Denied):
            self.assess()
        for raw in (b'{"risk":"R0","risk":"R4"}', b'{"value":NaN}', b'{}' * (C.MAX_INPUT // 2 + 1)):
            with self.assertRaises(C.Denied):
                C.decode(raw)

    def test_signer_scope_is_checked_before_description_or_restriction(self):
        self.registry['keys']['owner-key']['maximum_mode']='safe'
        authority=grant(self.registry,self.keys)
        with self.assertRaises(C.Denied):
            C.validate_grant(authority,self.registry,self.now,SUBJECT)
        self.registry['keys']['owner-key']['maximum_mode']='full-auto'
        self.registry['keys']['owner-key']['maximum_risk']='R1'
        with self.assertRaises(C.Denied):
            C.validate_grant(grant(self.registry,self.keys),self.registry,self.now,SUBJECT)

    def test_worker_uid_and_primary_gid_cannot_span_target_domains(self):
        self.registry['targets']['other-target']=copy.deepcopy(self.registry['targets']['fixture-target'])
        self.registry['tasks']['other-task']=copy.deepcopy(self.registry['tasks']['inspect-task'])
        self.registry['tasks']['other-task']['target_id']='other-target'
        for field in ('worker_uid','worker_gid'):
            candidate=copy.deepcopy(self.registry)
            candidate['tasks']['other-task']['worker_uid' if field=='worker_gid' else 'worker_gid']=1002
            with self.subTest(field=field),self.assertRaises(C.Denied): C.validate_registry(candidate)

    def test_arbitrary_legacy_executor_is_removed_even_with_fabricated_request(self):
        with tempfile.TemporaryDirectory(dir=ROOT.parent) as directory:
            marker = Path(directory) / "must-not-exist"
            plan = Path(directory) / "fake.json"
            plan.write_text('{"risk":"R0","approvals":[]}', encoding="utf-8")
            result = subprocess.run([sys.executable, str(ROOT / "tools/devops_exec.py"), "--operation", str(plan), "--", sys.executable, "-c", f"from pathlib import Path;Path({str(marker)!r}).touch()"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 3)
            self.assertFalse(marker.exists())


class NativeGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("native_guard_unit", ROOT / "tools/hooks/codex_pretooluse_gate.py")
        cls.guard = importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.guard)

    def event(self, command, tool="Bash"):
        return {"hook_event_name": "PreToolUse", "cwd": str(ROOT), "session_id": "fixture-session", "tool_name": tool, "tool_input": {"command": command}}

    def test_shell_patch_code_connector_and_subagent_bypasses_are_denied(self):
        for tool in ("apply_patch", "Edit", "Write", "spawn_agent", "Agent", "exec", "mcp__python__run", "mcp__ssh__execute", "write_stdin", "request_permissions"):
            allowed, _ = self.guard.evaluate(self.event("anything", tool))
            self.assertFalse(allowed, tool)
        for command in ("python -c 'write()'", "bash -c 'anything'", "curl https://example.invalid", "echo test", "node -e 'write()'"):
            try:
                allowed, _ = self.guard.evaluate(self.event(command))
            except ValueError:
                allowed = False
            self.assertFalse(allowed, command)

    def test_canonical_posix_and_powershell_literals_preserve_metacharacters(self):
        argv = [str(Path(sys.executable).resolve()), "-I", "C:/a space/quote'&;+/script.py", "--value", "$literal`*.txt"]
        for windows in (False, True):
            self.assertEqual(self.guard.parse(self.guard.render(argv, windows), windows), argv)
            with self.assertRaises(ValueError):
                self.guard.parse(self.guard.render(argv, windows) + "; write()", windows)

    def test_native_hook_denial_uses_real_supported_wire_shape(self):
        result = subprocess.run([sys.executable, str(ROOT / "tools/hooks/codex_pretooluse_gate.py")], input=json.dumps(self.event("python -c 'write()'")), capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        body = json.loads(result.stdout)
        self.assertEqual(body["hookSpecificOutput"]["permissionDecision"], "deny")
        self.assertEqual(body["hookSpecificOutput"]["hookEventName"], "PreToolUse")
        self.assertNotIn("continue", body)


class BrokerJournalTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="broker-unit-", dir=ROOT.parent)
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.registry, self.keys = registry()
        self.grant = grant(self.registry, self.keys)
        self.registry_path = self.root / "registry.json"
        self.registry_path.write_bytes(C.canonical(self.registry))
        for name in ("bundle", "state", "workers"):
            (self.root / name).mkdir()
        spec = importlib.util.spec_from_file_location("broker_journal_unit_" + self.root.name.replace("-", "_"), ROOT / "tools/broker_server.py")
        self.server = importlib.util.module_from_spec(spec); spec.loader.exec_module(self.server)
        self.broker = self.server.Broker(self.registry_path, self.root / "bundle", self.root / "state", self.root / "workers")
        self.addCleanup(self.broker.close)
        self.processes = []

        def snapshot(task, registry, call, run_dir):
            return ["never-a-real-executable"], {}, b"{}"

        def launch(argv, environment, payload, run_dir, task, final_check):
            with self.broker.admission_lock:
                try:
                    final_check()
                except Exception:
                    raise self.server.NotLaunched("fixture final admission refused") from None
                self.processes.append(argv)
            return {"status": "executed", "exit_code": 0, "result_valid": True, "result": {"state": "after"}}

        self.snapshot_patch = mock.patch.object(self.broker, "snapshot", side_effect=snapshot)
        self.launch_patch = mock.patch.object(self.broker, "launch", side_effect=launch)
        read_regular = self.server.regular
        executable = Path(sys.executable).resolve()
        self.regular_patch = mock.patch.object(self.server, "regular", side_effect=lambda path, maximum: executable.read_bytes() if Path(path) == executable else read_regular(path, maximum))
        for patcher in (self.snapshot_patch, self.launch_patch, self.regular_patch):
            patcher.start(); self.addCleanup(patcher.stop)

    def packet(self, operation="ops-journal-fixture", authority=None, task="configure-task", exact=None):
        return {"call": call(task, operation=operation), "grant": authority or self.grant, "admission": exact}

    def dispatch(self, route, packet):
        return self.broker.dispatch(route, packet, SUBJECT)

    def test_durable_journal_idempotency_and_conflicting_retry(self):
        packet = self.packet()
        first = self.dispatch("execute", packet)
        second = self.dispatch("execute", packet)
        self.assertEqual(first["status"], "executed")
        self.assertTrue(second["replayed"])
        self.assertEqual(len(self.processes), 1)
        packet["call"]["parameters"]["value"] = "before"
        with self.assertRaises(ValueError):
            self.dispatch("execute", packet)

    def test_intent_sync_failure_never_launches(self):
        original = self.server.atomic
        def atomic(path, value):
            if value.get("status") == "launch_intent":
                raise OSError("injected storage failure")
            return original(path, value)
        with mock.patch.object(self.server, "atomic", side_effect=atomic), self.assertRaises(OSError):
            self.dispatch("execute", self.packet())
        self.assertFalse(self.processes)

    def test_post_launch_journal_failure_freezes_new_mutations_and_preserves_intent(self):
        original = self.server.atomic
        def atomic(path, value):
            if value.get("status") == "executed":
                raise OSError("injected completion failure")
            return original(path, value)
        with mock.patch.object(self.server, "atomic", side_effect=atomic):
            result = self.dispatch("execute", self.packet())
        self.assertEqual(result["status"], "outcome_unknown")
        self.assertEqual(len(self.processes), 1)
        journal = C.read_record(self.root / "state/journal/ops-journal-fixture.json")
        self.assertEqual(journal["status"], "launch_intent")
        with self.assertRaises(ValueError):
            self.dispatch("execute", self.packet(operation="ops-new-retry-key"))
        self.assertEqual(len(self.processes), 1)

    def test_safe_is_durable_while_execution_lock_is_busy_and_cancels_overlapping_grants(self):
        self.broker.mutex.acquire()
        try:
            result = self.dispatch("restrict", {"mode": "safe", "grant": None})
        finally:
            self.broker.mutex.release()
        self.assertEqual(result["mode"], "safe")
        for authority in (self.grant, grant(self.registry, self.keys, identifier="grant-overlapping-two")):
            with self.assertRaises(ValueError):
                self.dispatch("execute", self.packet(authority=authority))
        self.assertFalse(self.processes)

    def test_safe_after_intent_stops_final_admission_before_process(self):
        original = self.server.atomic
        def atomic(path, value):
            original(path, value)
            if value.get("status") == "launch_intent":
                self.dispatch("restrict", {"mode": "safe", "grant": None})
        with mock.patch.object(self.server, "atomic", side_effect=atomic):
            result = self.dispatch("execute", self.packet())
        self.assertEqual(result["status"], "blocked_before_launch")
        self.assertFalse(self.processes)

    def test_safe_storage_failure_poison_latch_prevents_all_later_admission(self):
        with mock.patch.object(self.server, "atomic", side_effect=OSError("injected safe persistence failure")), self.assertRaises(OSError):
            self.dispatch("restrict", {"mode": "safe", "grant": None})
        with self.assertRaises(ValueError):
            self.dispatch("execute", self.packet())
        self.assertFalse(self.processes)

    def test_balanced_restriction_cannot_be_raised_by_old_grant_or_old_exact_ticket(self):
        authority = grant(self.registry, self.keys, mode="semi-auto")
        self.dispatch("restrict", {"mode": "balanced", "grant": authority})
        self.dispatch("execute", self.packet(authority=authority))
        with self.assertRaises(ValueError):
            self.dispatch("restrict", {"mode": "semi-auto", "grant": authority})
        request = call("production-task")
        exact = admission(self.registry, self.keys, request, authority)
        with self.assertRaises(ValueError):
            self.dispatch("execute", {"call": request, "grant": authority, "admission": exact})
        state = self.broker.principal_state(self.registry, SUBJECT)
        renewed = grant(self.registry, self.keys, mode="semi-auto", epoch=state["epoch"])
        result = self.dispatch("execute", self.packet(operation="ops-new-authority", task="production-task", authority=renewed))
        self.assertEqual(result["status"], "executed")

    def test_status_survives_expiry_and_does_not_replay_execution(self):
        self.dispatch("execute", self.packet())
        class ExpiredClock:
            @staticmethod
            def now(tz):
                return datetime.now(timezone.utc) + timedelta(days=10)
        with mock.patch.object(self.server, "datetime", ExpiredClock):
            result = self.dispatch("status", {"operation_id": "ops-journal-fixture"})
            with self.assertRaises(ValueError):
                self.dispatch("execute", self.packet())
        self.assertEqual(result["status"], "executed")
        self.assertEqual(len(self.processes), 1)
        with self.assertRaises(ValueError):
            self.broker.dispatch("status", {"operation_id": "ops-journal-fixture"}, "sha256:" + "f" * 64)

    def test_unclean_shutdown_requires_owner_reconciliation(self):
        self.broker.poisoned = True
        self.broker.close()
        with self.assertRaises(ValueError):
            self.server.Broker(self.registry_path, self.root / "bundle", self.root / "state", self.root / "workers")

    def test_safe_covers_certificate_aliases_and_cannot_be_raised_through_restrict(self):
        alias='sha256:'+'c'*64
        self.registry['clients'][alias]=dict(self.registry['clients'][SUBJECT])
        self.registry_path.write_bytes(C.canonical(self.registry)); self.broker.clients=self.registry['clients']
        old=grant(self.registry,self.keys,mode='semi-auto')
        result=self.broker.dispatch('restrict',{'mode':'safe','grant':None},alias)
        for mode in ('balanced','semi-auto','full-auto'):
            renewed=grant(self.registry,self.keys,mode=mode,epoch=result['current_epoch'])
            with self.subTest(mode=mode),self.assertRaises(ValueError):
                self.dispatch('restrict',{'mode':mode,'grant':renewed})
        with self.assertRaises(ValueError): self.dispatch('execute',self.packet(authority=old))
        renewed=grant(self.registry,self.keys,epoch=result['current_epoch'])
        self.assertEqual(self.dispatch('execute',self.packet(authority=renewed))['status'],'executed')
        with self.assertRaises(ValueError): self.dispatch('execute',self.packet(operation='ops-old-epoch-after-renewal',authority=old))

    def test_operation_budget_and_invalid_result_keep_mutations_closed(self):
        payload=copy.deepcopy(self.grant); payload['max_operations']=1
        authority=signed(payload,self.keys)
        self.dispatch('execute',self.packet(authority=authority))
        with self.assertRaises(ValueError): self.dispatch('execute',self.packet(operation='ops-budget-exhausted',authority=authority))
        def invalid(*args):
            args[-1]()
            return {'status':'outcome_unknown','exit_code':0,'result_valid':False,'result':None}
        with mock.patch.object(self.broker,'launch',side_effect=invalid):
            result=self.dispatch('execute',self.packet(operation='ops-invalid-result'))
        self.assertEqual(result['status'],'outcome_unknown')
        with self.assertRaises(ValueError): self.dispatch('execute',self.packet(operation='ops-after-invalid-result'))

    def test_new_directory_ancestors_are_synced_and_corrupt_audit_refuses(self):
        directory=self.root/'new-parent'/'nested'
        synced=[]
        with mock.patch.object(self.server.LOCK,'sync_directory',side_effect=lambda path:synced.append(path)):
            self.server.atomic(directory/'record.json',{'ok':True})
        for parent in (directory,directory.parent,self.root): self.assertIn(parent,synced)
        self.broker.audit_append('fixture-event',{'redacted':True})
        with (self.root/'state/audit.jsonl').open('ab') as stream: stream.write(b'{}\n')
        with self.assertRaises(ValueError): self.broker.audit_verify()


class BrokerClientResultTests(unittest.TestCase):
    def test_uncertain_http_responses_after_execute_never_claim_prelaunch_refusal(self):
        spec=importlib.util.spec_from_file_location('broker_client_result',ROOT/'tools/devops_exec.py')
        client=importlib.util.module_from_spec(spec); spec.loader.exec_module(client)
        config={'url':'https://fixture.invalid','ca_file':'C:/fixture/ca' if os.name=='nt' else '/fixture/ca',
                'client_certificate':'C:/fixture/cert' if os.name=='nt' else '/fixture/cert','client_private_key':'C:/fixture/key' if os.name=='nt' else '/fixture/key','timeout_seconds':3}
        for status,body in ((200,b'invalid'),(200,b'{}'),(403,b'[]'),(503,b'{}'),(200,b'{"status":"prepared"}')):
            response=mock.Mock(status=status); response.read.return_value=body
            connection=mock.Mock(); connection.getresponse.return_value=response
            with self.subTest(status=status,body=body),mock.patch.object(client.ssl,'create_default_context'),mock.patch.object(client.http.client,'HTTPSConnection',return_value=connection):
                self.assertEqual(client.call_broker(config,{},'execute')['status'],'outcome_unknown')


if __name__ == "__main__":
    unittest.main()
