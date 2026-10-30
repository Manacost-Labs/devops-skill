"""Offline AWS launch reconciliation, using native DescribeInstances shapes."""
import contextlib
import copy
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("aws_launch_inspection", ROOT / "cloud-aws/scripts/inspect-launch.py")
AWS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AWS)


class AwsLaunchInspectionTests(unittest.TestCase):
    def setUp(self):
        self.checklist = {
            "account_id": "123456789012", "partition": "aws", "region": "eu-west-1",
            "client_token": "retained-operation-token", "count": 1,
            "image_id": "ami-0123456789abcdef0", "instance_type": "t3.micro",
            "subnet_id": "subnet-0123456789abcdef0", "security_group_ids": ["sg-0123456789abcdef0"],
        }
        self.instance = {
            "InstanceId": "i-0123456789abcdef0", "ClientToken": self.checklist["client_token"],
            "ImageId": self.checklist["image_id"], "InstanceType": "t3.micro",
            "SubnetId": self.checklist["subnet_id"],
            "SecurityGroups": [{"GroupId": "sg-0123456789abcdef0", "GroupName": "irrelevant"}],
            "State": {"Name": "running", "Code": 16},
        }
        self.capture = {
            "account_id": "123456789012", "partition": "aws", "region": "eu-west-1",
            "response": {"Reservations": [{"OwnerId": "123456789012", "Instances": [self.instance]}]},
        }

    def test_running_match_is_never_authority_or_service_acceptance(self):
        result = AWS.inspect(self.checklist, self.capture)
        self.assertEqual(result["observation"], "control_plane_match")
        for field in ("retry_authorized", "service_health_verified", "full_plan_verified"):
            self.assertIs(result[field], False)

    def test_empty_read_remains_unobserved(self):
        self.capture["response"]["Reservations"] = []
        result = AWS.inspect(self.checklist, self.capture)
        self.assertEqual(result["observation"], "unobserved")
        self.assertFalse(result["retry_authorized"])

    def test_pending_partial_and_terminal_results(self):
        self.instance["State"]["Name"] = "pending"
        self.instance["State"]["Code"] = 0
        self.assertEqual(AWS.inspect(self.checklist, self.capture)["observation"], "pending")
        self.checklist["count"] = 2
        self.assertEqual(AWS.inspect(self.checklist, self.capture)["observation"], "partial")
        for state in ("shutting-down", "terminated", "stopping", "stopped"):
            self.instance["State"]["Name"] = state
            self.instance["State"]["Code"] = AWS.STATE_CODES[state]
            self.assertEqual(AWS.inspect(self.checklist, self.capture)["observation"], "terminal")

    def test_scope_owner_and_material_mismatch_rejected(self):
        cases = [
            ("account_id", "999999999999"), ("partition", "aws-cn"), ("region", "eu-west-2"),
        ]
        for field, value in cases:
            with self.subTest(field=field):
                capture = copy.deepcopy(self.capture)
                capture[field] = value
                with self.assertRaises(ValueError):
                    AWS.inspect(self.checklist, capture)
        for field in ("ClientToken", "ImageId", "InstanceType", "SubnetId"):
            with self.subTest(field=field):
                capture = copy.deepcopy(self.capture)
                capture["response"]["Reservations"][0]["Instances"][0][field] = "foreign"
                with self.assertRaises(ValueError):
                    AWS.inspect(self.checklist, capture)
        self.capture["response"]["Reservations"][0]["OwnerId"] = "999999999999"
        with self.assertRaises(ValueError):
            AWS.inspect(self.checklist, self.capture)

    def test_truncated_duplicate_extra_and_malformed_observations_rejected(self):
        for value in (None, "", "next-page"):
            capture = copy.deepcopy(self.capture)
            capture["response"]["NextToken"] = value
            with self.assertRaises(ValueError):
                AWS.inspect(self.checklist, capture)
        self.capture["response"]["Reservations"][0]["Instances"].append(copy.deepcopy(self.instance))
        with self.assertRaises(ValueError):
            AWS.inspect(self.checklist, self.capture)
        self.capture["response"]["Reservations"][0]["Instances"][1]["InstanceId"] = "i-1123456789abcdef0"
        with self.assertRaises(ValueError):
            AWS.inspect(self.checklist, self.capture)
        self.capture["response"]["Reservations"] = [{}]
        with self.assertRaises(ValueError):
            AWS.inspect(self.checklist, self.capture)

    def test_security_group_union_and_duplicate_fail_closed(self):
        for groups in ([], [{"GroupId": "sg-1123456789abcdef0"}], self.instance["SecurityGroups"] * 2, [None]):
            self.instance["SecurityGroups"] = groups
            with self.assertRaises(ValueError):
                AWS.inspect(self.checklist, self.capture)

    def test_unknown_fields_boolean_count_and_state_do_not_pass(self):
        for field, value in (("count", True), ("count", 101), ("count", 0), ("client_token", "bad\n"), ("ImageId", "unknown")):
            checklist = dict(self.checklist)
            checklist[field] = value
            with self.assertRaises(ValueError):
                AWS.inspect(checklist, self.capture)
        self.instance["State"]["Name"] = ["running"]
        with self.assertRaises(ValueError):
            AWS.inspect(self.checklist, self.capture)

    def test_error_responses_and_contradictory_native_state_rejected(self):
        for field, value in (("Error", {"Code": "AuthFailure"}), ("Errors", []), ("ResponseMetadata", {"HTTPStatusCode": 500}), ("ResponseMetadata", {"HTTPStatusCode": True})):
            capture = copy.deepcopy(self.capture)
            capture["response"][field] = value
            with self.assertRaises(ValueError):
                AWS.inspect(self.checklist, capture)
        self.instance["State"]["Code"] = 48
        with self.assertRaises(ValueError):
            AWS.inspect(self.checklist, self.capture)
        self.instance["State"]["Code"] = 16 + 256
        self.assertEqual(AWS.inspect(self.checklist, self.capture)["observation"], "control_plane_match")

    def test_oversized_capture_read_is_bounded_before_decoding(self):
        class BoundedStream(io.BytesIO):
            def read(self, size=-1):
                if size < 0 or size > AWS.MAX_INPUT_BYTES + 1:
                    raise AssertionError("unbounded read of untrusted evidence")
                return super().read(size)

        with patch.object(AWS.Path, "open", return_value=BoundedStream(b" " * (AWS.MAX_INPUT_BYTES + 2))):
            with self.assertRaisesRegex(ValueError, "inspection bound"):
                AWS.load_json("unused")

    def test_cli_exit_status_and_redacted_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            checklist = Path(directory) / "checklist.json"
            capture = Path(directory) / "capture.json"
            checklist.write_text(json.dumps(self.checklist), encoding="utf-8")
            capture.write_text(json.dumps(self.capture), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(AWS.main(["--checklist", str(checklist), "--capture", str(capture)]), 0)
            self.capture["response"]["Reservations"] = []
            capture.write_text(json.dumps(self.capture), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(AWS.main(["--checklist", str(checklist), "--capture", str(capture)]), 2)
            capture.write_text('{"secret":"synthetic","secret":"other"}', encoding="utf-8")
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream):
                self.assertEqual(AWS.main(["--checklist", str(checklist), "--capture", str(capture)]), 1)
            self.assertNotIn("synthetic", stream.getvalue())
            self.assertNotIn(str(capture), stream.getvalue())


if __name__ == "__main__":
    unittest.main()
