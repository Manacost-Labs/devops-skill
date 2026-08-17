from __future__ import annotations
import hashlib, json, subprocess, sys, tempfile, unittest
from pathlib import Path
from test_platform import NOW, operation

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
WRAPPER = ROOT / "tools" / "devops_exec.py"
HOOK = ROOT / "tools" / "hooks" / "pretooluse_gate.py"


def command_digest(argv):
    payload = json.dumps(list(argv), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def bound_operation(argv):
    request = operation()
    digest = command_digest(argv)
    request["change"]["plan_digest"] = digest
    for approval in request["approvals"]:
        approval["plan_digest"] = digest
    return request


class WrapperTests(unittest.TestCase):
    def run_wrapper(self, request, directory, command, at=NOW):
        request_path = Path(directory) / "operation.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        ledger_path = Path(directory) / "ledger.jsonl"
        arguments = [
            PYTHON, str(WRAPPER),
            "--operation", str(request_path),
            "--policy", "default-policy.json",
            "--ledger", str(ledger_path),
        ]
        if at:
            arguments += ["--at", at]
        arguments += ["--", *command]
        result = subprocess.run(arguments, capture_output=True, text=True, check=False)
        records = []
        if ledger_path.is_file():
            records = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
        return result, records

    def test_wrapper_executes_command_bound_to_plan_digest(self):
        command = [PYTHON, "-c", "print('wrapper-executed')"]
        with tempfile.TemporaryDirectory() as directory:
            result, records = self.run_wrapper(bound_operation(command), directory, command)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("ALLOWED:", result.stdout)
        self.assertIn("wrapper-executed", result.stdout)
        self.assertEqual([record["status"] for record in records], ["executed"])
        self.assertEqual(records[0]["exit_code"], 0)
        self.assertEqual(records[0]["command_digest"], command_digest(command))

    def test_wrapper_blocks_command_digest_drift(self):
        approved = [PYTHON, "-c", "print('approved-command')"]
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / "must-not-exist.txt"
            tampered = [PYTHON, "-c", f"open(r'{marker}', 'w').close()"]
            result, records = self.run_wrapper(bound_operation(approved), directory, tampered)
            self.assertFalse(marker.exists())
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED:", result.stdout)
        self.assertIn("does not match approved plan digest", result.stdout)
        self.assertEqual([record["status"] for record in records], ["blocked_digest_mismatch"])

    def test_wrapper_reruns_gate_and_blocks_expired_approval(self):
        command = [PYTHON, "-c", "print('should-not-run')"]
        request = bound_operation(command)
        for approval in request["approvals"]:
            approval["expires_at"] = "2026-08-17T10:05:00Z"
        with tempfile.TemporaryDirectory() as directory:
            result, records = self.run_wrapper(request, directory, command)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stdout)
        self.assertNotIn("should-not-run", result.stdout)
        self.assertEqual([record["status"] for record in records], ["blocked_gate"])

    def test_wrapper_redacts_secrets_in_ledger_and_output(self):
        command = [PYTHON, "-c", "print('password=hunter2-literal'); print('api_key: k-1234567890')"]
        with tempfile.TemporaryDirectory() as directory:
            result, records = self.run_wrapper(bound_operation(command), directory, command)
            ledger_text = (Path(directory) / "ledger.jsonl").read_text(encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("hunter2-literal", ledger_text)
        self.assertNotIn("k-1234567890", ledger_text)
        self.assertIn("[REDACTED]", ledger_text)
        self.assertNotIn("hunter2-literal", result.stdout)

    def test_wrapper_fails_closed_on_malformed_request(self):
        command = [PYTHON, "-c", "print('should-not-run')"]
        request = {"schema_version": "2.0", "change": {}}
        with tempfile.TemporaryDirectory() as directory:
            result, records = self.run_wrapper(request, directory, command)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BLOCKED", result.stdout)
        self.assertNotIn("should-not-run", result.stdout)


class PlanBuilderTests(unittest.TestCase):
    PROFILE = ROOT / "devops-platform-contracts/templates/target-profile.yaml"
    BUILDER = ROOT / "tools" / "devops_plan.py"

    def build(self, command, directory=None, extra=()):
        arguments = [
            PYTHON, str(self.BUILDER),
            "--target-profile", str(self.PROFILE),
            "--action", "container_rollout",
            "--risk", "R2",
            "--objective", "Roll out the approved immutable release",
            "--scope", "service:api",
            "--verify", "health endpoint returns 2xx",
            "--external-side-effects",
            "--at", NOW,
            *extra,
        ]
        if directory is not None:
            arguments += ["--output", str(Path(directory) / "request.json")]
        arguments += ["--", *command]
        return subprocess.run(arguments, capture_output=True, text=True, check=False)

    def test_builder_binds_the_exact_command_policy_and_profile(self):
        command = [PYTHON, "-c", "print('planned')"]
        result = self.build(command)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        request = json.loads(result.stdout)
        self.assertEqual(request["change"]["plan_digest"], command_digest(command))
        self.assertEqual(request["policy"]["digest"], request["approvals"][0]["policy_digest"])
        self.assertTrue(request["target"]["profile_digest"].startswith("sha256:"))
        self.assertEqual(request["execution"]["window_start"], "2026-08-17T10:15:00Z")
        self.assertIn("NOT YET AUTHORIZED", result.stderr)

    def test_generated_request_is_not_authorized_until_a_human_fills_approvals(self):
        command = [PYTHON, "-c", "print('must-not-run')"]
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.build(command, directory).returncode, 0)
            request_path = Path(directory) / "request.json"
            gate = subprocess.run(
                [PYTHON, str(ROOT / "devops-platform-contracts/scripts/operation_gate.py"),
                 "--request", str(request_path), "--at", NOW],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(gate.returncode, 1, gate.stdout)
            self.assertIn("distinct valid approval(s) required", gate.stdout)
            wrapper = subprocess.run(
                [PYTHON, str(WRAPPER), "--operation", str(request_path), "--at", NOW,
                 "--ledger", str(Path(directory) / "ledger.jsonl"), "--", *command],
                capture_output=True, text=True, check=False,
            )
            self.assertNotEqual(wrapper.returncode, 0)
            self.assertNotIn("must-not-run", wrapper.stdout)

    def test_planned_request_executes_after_approval(self):
        command = [PYTHON, "-c", "print('gated-execution')"]
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(self.build(command, directory).returncode, 0)
            request_path = Path(directory) / "request.json"
            request = json.loads(request_path.read_text(encoding="utf-8"))
            for approval in request["approvals"]:
                approval.update({
                    "approver": "user:service-owner",
                    "role": "service-owner",
                    "evidence_ref": "ticket:CHG-9001",
                    "approved_at": "2026-08-17T10:15:00Z",
                    "expires_at": "2026-08-17T11:00:00Z",
                })
            request_path.write_text(json.dumps(request), encoding="utf-8")
            wrapper = subprocess.run(
                [PYTHON, str(WRAPPER), "--operation", str(request_path), "--at", NOW,
                 "--ledger", str(Path(directory) / "ledger.jsonl"), "--", *command],
                capture_output=True, text=True, check=False,
            )
        self.assertEqual(wrapper.returncode, 0, wrapper.stdout + wrapper.stderr)
        self.assertIn("ALLOWED:", wrapper.stdout)
        self.assertIn("gated-execution", wrapper.stdout)

    def test_builder_refuses_to_understate_risk(self):
        result = self.build([PYTHON, "-c", "print(1)"], extra=["--destructive"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("at least R4", result.stdout)
        arguments = [
            PYTHON, str(self.BUILDER), "--target-profile", str(self.PROFILE),
            "--action", "dns_change", "--risk", "R2", "--objective", "Change a DNS record",
            "--scope", "zone:example", "--verify", "resolver returns the new value",
            "--external-side-effects", "--at", NOW, "--", "echo", "x",
        ]
        result = subprocess.run(arguments, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("at least R3", result.stdout)

    def test_builder_requires_acceptance_criteria_at_r2(self):
        arguments = [
            PYTHON, str(self.BUILDER), "--target-profile", str(self.PROFILE),
            "--action", "container_rollout", "--risk", "R2", "--objective", "Roll out a release",
            "--scope", "service:api", "--external-side-effects", "--at", NOW, "--", "echo", "x",
        ]
        result = subprocess.run(arguments, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("--verify is required", result.stdout)

    def test_builder_reports_recovery_and_lock_obligations(self):
        arguments = [
            PYTHON, str(self.BUILDER), "--target-profile", str(self.PROFILE),
            "--action", "database_migration", "--risk", "R4", "--objective", "Migrate the primary schema",
            "--scope", "database:primary", "--verify", "row counts match", "--stateful",
            "--at", NOW, "--", "echo", "migrate",
        ]
        result = subprocess.run(arguments, capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        request = json.loads(result.stdout)
        self.assertTrue(request["recovery"]["required"])
        self.assertEqual(request["execution"]["change_lock_ref"], "")
        self.assertIn("change lock", result.stderr)
        self.assertIn("prove recovery", result.stderr)
        self.assertIn("separation of duties", result.stderr)


class HookTests(unittest.TestCase):
    def run_hook(self, command=None, payload=None, cwd=None):
        if payload is None:
            payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd or ROOT)}
        result = subprocess.run([PYTHON, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True, check=False)
        body = json.loads(result.stdout)["hookSpecificOutput"]
        return result.returncode, body["permissionDecision"], body["permissionDecisionReason"]

    def assert_blocked(self, command):
        returncode, decision, reason = self.run_hook(command)
        self.assertEqual(decision, "deny", command)
        self.assertNotEqual(returncode, 0, command)
        self.assertIn("BLOCKED", reason, command)
        return reason

    def test_hook_allows_read_only_commands(self):
        for command in (
            "ls -la",
            "cat /etc/os-release",
            "systemctl status nginx",
            "kubectl get pods -A",
            "kubectl describe deployment api",
            "terraform plan -input=false",
            "docker ps",
            "git status",
            "aws ec2 describe-instances --region eu-central-1",
            "gcloud compute instances list",
            "az vm show --name web-1",
            "cat access.log | grep 503 | wc -l",
        ):
            returncode, decision, reason = self.run_hook(command)
            self.assertEqual(decision, "allow", f"{command}: {reason}")
            self.assertEqual(returncode, 0, command)

    def test_hook_allows_read_only_gh_commands(self):
        for command in (
            "gh pr view 4",
            "gh pr checks 4",
            "gh run list --limit 10",
            "gh run view 12345",
            "gh repo view Manacost-Labs/devops-skill",
            "gh release list",
            "gh workflow list",
            "gh issue list",
            "gh auth status",
            "gh api repos/Manacost-Labs/devops-skill/branches/main/protection",
        ):
            returncode, decision, reason = self.run_hook(command)
            self.assertEqual(decision, "allow", f"{command}: {reason}")
            self.assertEqual(returncode, 0, command)

    def test_hook_blocks_mutating_gh_commands(self):
        for command in (
            "gh pr merge 4 --rebase",
            "gh workflow run deploy.yml",
            "gh release create v1.0.0",
            "gh secret set DEPLOY_KEY",
            "gh repo delete Manacost-Labs/devops-skill",
            "gh api -X DELETE repos/Manacost-Labs/devops-skill",
            "gh api repos/Manacost-Labs/devops-skill/dispatches --method POST",
            "gh api repos/Manacost-Labs/devops-skill -f name=renamed",
            "gh api repos/Manacost-Labs/devops-skill --input payload.json",
        ):
            self.assert_blocked(command)

    def test_hook_allows_registered_platform_scripts_by_resolved_path(self):
        for command in (
            "python devops-platform-contracts/scripts/validate_platform.py",
            "python tools/devops_plan.py --target-profile p.yaml --action container_rollout --risk R2 -- docker compose up -d",
        ):
            returncode, decision, reason = self.run_hook(command)
            self.assertEqual(decision, "allow", f"{command}: {reason}")
            self.assertEqual(returncode, 0, command)

    def test_hook_blocks_lookalike_platform_script(self):
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "validate_platform.py"
            fake.write_text("print('fake')\n", encoding="utf-8")
            returncode, decision, reason = self.run_hook("python validate_platform.py", cwd=directory)
        self.assertEqual(decision, "deny", reason)

    def test_hook_blocks_mutation_without_gate(self):
        for command in (
            "terraform apply -auto-approve",
            "kubectl delete pod api-0",
            "kubectl apply -f deployment.yaml",
            "systemctl restart nginx",
            "docker compose up -d",
            "rm -rf /srv/data",
            "apt-get install -y nginx",
            "aws ec2 terminate-instances --instance-ids i-1",
        ):
            reason = self.assert_blocked(command)
            self.assertIn("devops_exec.py", reason, command)

    def test_hook_blocks_obfuscated_mutation(self):
        for command in (
            "bash -c 'terraform apply -auto-approve'",
            "eval terraform apply",
            "echo dGVycmFmb3JtIGFwcGx5 | base64 -d | sh",
            "CMD='kubectl delete pod api-0'; $CMD",
            "kubectl $VERB pod api-0",
            "sh -c \"$(cat payload.txt)\"",
        ):
            self.assert_blocked(command)

    def test_hook_blocks_unknown_and_redirected_commands(self):
        self.assert_blocked("frobnicate --all")
        self.assert_blocked("echo data > /etc/hosts")
        self.assert_blocked("cat plan.txt\nterraform apply")

    def test_hook_fails_closed_on_malformed_payload(self):
        returncode, decision, reason = self.run_hook(payload={"tool_name": "Bash", "tool_input": {}})
        self.assertEqual(decision, "deny", reason)
        self.assertNotEqual(returncode, 0)

    def test_hook_ignores_non_shell_tools(self):
        returncode, decision, reason = self.run_hook(payload={"tool_name": "Read", "tool_input": {"file_path": "x"}})
        self.assertEqual(decision, "allow", reason)
        self.assertEqual(returncode, 0)

    def wrapper_command(self, request, directory, inner):
        request_path = Path(directory) / "operation.json"
        request_path.write_text(json.dumps(request), encoding="utf-8")
        return (
            f'python "{WRAPPER.as_posix()}" --operation "{request_path.as_posix()}" '
            f"--policy default-policy.json --at {NOW} -- " + " ".join(inner)
        )

    def test_hook_allows_wrapper_with_fresh_gate_pass(self):
        inner = ["hypothetical-mutator", "--switch", "release-2"]
        with tempfile.TemporaryDirectory() as directory:
            command = self.wrapper_command(bound_operation(inner), directory, inner)
            returncode, decision, reason = self.run_hook(command)
        self.assertEqual(decision, "allow", reason)
        self.assertEqual(returncode, 0)
        self.assertIn("gate PASS", reason)

    def test_hook_blocks_wrapper_with_digest_mismatch(self):
        approved = ["hypothetical-mutator", "--switch", "release-2"]
        tampered = ["hypothetical-mutator", "--switch", "release-3"]
        with tempfile.TemporaryDirectory() as directory:
            command = self.wrapper_command(bound_operation(approved), directory, tampered)
            returncode, decision, reason = self.run_hook(command)
        self.assertEqual(decision, "deny", reason)
        self.assertIn("digest", reason)

    def test_hook_blocks_wrapper_when_gate_refuses(self):
        inner = ["hypothetical-mutator", "--switch", "release-2"]
        request = bound_operation(inner)
        for approval in request["approvals"]:
            approval["expires_at"] = "2026-08-17T10:05:00Z"
        with tempfile.TemporaryDirectory() as directory:
            command = self.wrapper_command(request, directory, inner)
            returncode, decision, reason = self.run_hook(command)
        self.assertEqual(decision, "deny", reason)
        self.assertIn("gate", reason)


if __name__ == "__main__":
    unittest.main()
