from __future__ import annotations
import hashlib, json, subprocess, sys, tempfile, unittest
from pathlib import Path
from test_platform import NOW, operation

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
WRAPPER = ROOT / "tools" / "devops_exec.py"


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


if __name__ == "__main__":
    unittest.main()
