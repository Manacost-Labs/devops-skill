"""Offline native Azure-AsyncOperation and VM-incarnation evidence checks."""
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
SPEC = importlib.util.spec_from_file_location("azure_vm_inspection", ROOT / "cloud-azure/scripts/inspect-vm-operation.py")
AZURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AZURE)


class AzureVmObservationTests(unittest.TestCase):
    def setUp(self):
        self.subscription = "11111111-1111-4111-8111-111111111111"
        self.resource_id = f"/subscriptions/{self.subscription}/resourceGroups/fixture/providers/Microsoft.Compute/virtualMachines/api"
        self.operation_path = f"/subscriptions/{self.subscription}/providers/Microsoft.Compute/locations/eastus/operations/33333333-3333-4333-8333-333333333333"
        self.checklist = {
            "cloud": "AzureCloud", "tenant_id": "22222222-2222-4222-8222-222222222222",
            "subscription_id": self.subscription, "resource_id": self.resource_id,
            "vm_id": "44444444-4444-4444-8444-444444444444", "location": "eastus",
            "operation_url": f"https://management.azure.com{self.operation_path}?api-version=2025-04-01",
        }
        self.capture = {
            **{key: self.checklist[key] for key in ("cloud", "tenant_id", "subscription_id", "operation_url")},
            "poll_http_status": 200, "poll_body": {"status": "Succeeded", "id": self.operation_path},
            "resource_http_status": 200,
            "resource_body": {
                "id": self.resource_id, "type": "Microsoft.Compute/virtualMachines", "location": "eastus",
                "properties": {"vmId": self.checklist["vm_id"], "provisioningState": "Succeeded"},
            },
        }

    def assert_no_authority(self, result):
        for key in ("retry_authorized", "cleanup_authorized", "service_health_verified", "full_plan_verified"):
            self.assertIs(result[key], False)

    def test_matching_subset_is_not_health_ownership_or_execution_authority(self):
        result = AZURE.inspect(self.checklist, self.capture)
        self.assertEqual(result["observation"], "control_plane_match")
        self.assert_no_authority(result)

    def test_pending_failed_and_resource_pending_never_pass(self):
        for status in ("InProgress", "Running", "Accepted", "ProviderSpecificState"):
            self.capture["poll_body"]["status"] = status
            result = AZURE.inspect(self.checklist, self.capture)
            self.assertEqual(result["observation"], "pending")
            self.assert_no_authority(result)
        for status in ("Failed", "Canceled"):
            self.capture["poll_body"]["status"] = status
            self.capture["poll_body"]["error"] = {"code": "SyntheticFailure", "message": "not disclosed"}
            self.assertEqual(AZURE.inspect(self.checklist, self.capture)["observation"], "failed")
        self.capture["poll_body"] = {"status": "Succeeded"}
        for status, result in (("Updating", "resource_pending"), ("Failed", "failed"), ("Canceled", "failed")):
            self.capture["resource_body"]["properties"]["provisioningState"] = status
            self.assertEqual(AZURE.inspect(self.checklist, self.capture)["observation"], result)

    def test_success_with_error_is_rejected(self):
        for error in ({"code": "SyntheticFailure"}, None, "malformed"):
            capture = copy.deepcopy(self.capture)
            capture["poll_body"]["error"] = error
            with self.assertRaises(ValueError):
                AZURE.inspect(self.checklist, capture)
        self.capture["resource_body"]["error"] = {"code": "SyntheticFailure"}
        with self.assertRaises(ValueError):
            AZURE.inspect(self.checklist, self.capture)

    def test_native_operation_name_is_checked_with_or_without_id(self):
        operation_name = self.operation_path.rsplit("/", 1)[1]
        self.capture["poll_body"] = {"status": "Succeeded", "name": operation_name}
        self.assertEqual(AZURE.inspect(self.checklist, self.capture)["observation"], "control_plane_match")
        for retained_id in (False, True):
            capture = copy.deepcopy(self.capture)
            if retained_id:
                capture["poll_body"]["id"] = self.operation_path
            for value in ("55555555-5555-4555-8555-555555555555", None, "", []):
                capture["poll_body"]["name"] = value
                with self.assertRaises(ValueError):
                    AZURE.inspect(self.checklist, capture)

    def test_pending_poll_does_not_hide_supplied_foreign_vm_evidence(self):
        for status in ("Running", "Failed"):
            capture = copy.deepcopy(self.capture)
            capture["poll_body"]["status"] = status
            capture["resource_body"]["properties"]["vmId"] = "55555555-5555-4555-8555-555555555555"
            with self.assertRaises(ValueError):
                AZURE.inspect(self.checklist, capture)

    def test_missing_or_unavailable_observations_never_establish_absence(self):
        for status in (None, 404, 429, 500, 202):
            capture = copy.deepcopy(self.capture)
            capture["poll_http_status"] = status
            capture["poll_body"] = None if status is None else {"error": {"code": "Unavailable"}}
            result = AZURE.inspect(self.checklist, capture)
            self.assertEqual(result["observation"], "poll_unavailable")
            self.assert_no_authority(result)
            capture = copy.deepcopy(self.capture)
            capture["resource_http_status"] = status
            capture["resource_body"] = None if status is None else {"error": {"code": "Unavailable"}}
            result = AZURE.inspect(self.checklist, capture)
            self.assertEqual(result["observation"], "resource_unobserved")
            self.assert_no_authority(result)

    def test_foreign_cloud_tenant_subscription_and_incarnation_rejected(self):
        for field, value in (("cloud", "AzureUSGovernment"), ("tenant_id", "55555555-5555-4555-8555-555555555555"), ("subscription_id", "55555555-5555-4555-8555-555555555555")):
            with self.subTest(field=field):
                capture = copy.deepcopy(self.capture)
                capture[field] = value
                with self.assertRaises(ValueError):
                    AZURE.inspect(self.checklist, capture)
        self.capture["resource_body"]["properties"]["vmId"] = "55555555-5555-4555-8555-555555555555"
        with self.assertRaises(ValueError):
            AZURE.inspect(self.checklist, self.capture)

    def test_poll_url_cannot_change_origin_scope_or_operation(self):
        legitimate = self.checklist["operation_url"]
        candidates = [
            legitimate.replace("management.azure.com", "management.azure.com.attacker.example"),
            legitimate.replace("management.azure.com", "management.usgovcloudapi.net"),
            legitimate.replace("https://", "http://"),
            legitimate.replace("https://", "https://user:synthetic@"),
            legitimate.replace("/eastus/", "/westus/"),
            legitimate.replace(self.subscription, "55555555-5555-4555-8555-555555555555"),
            legitimate.replace("33333333-3333-4333-8333-333333333333", "55555555-5555-4555-8555-555555555555"),
            legitimate + "#fragment", legitimate + "&api-version=2025-04-01",
            legitimate.replace("/operations/", "/operations/%2e%2e/"), legitimate + "\n",
        ]
        for candidate in candidates:
            with self.subTest(candidate=candidate):
                capture = copy.deepcopy(self.capture)
                capture["operation_url"] = candidate
                with self.assertRaises(ValueError):
                    AZURE.inspect(self.checklist, capture)
        # An attacker changing both envelopes still cannot use a foreign origin.
        for target in (self.capture, self.checklist):
            target["operation_url"] = candidates[0]
        with self.assertRaises(ValueError):
            AZURE.inspect(self.checklist, self.capture)

    def test_arm_identity_is_case_insensitive_but_other_objects_do_not_match(self):
        self.capture["resource_body"]["id"] = self.resource_id.upper()
        self.assertEqual(AZURE.inspect(self.checklist, self.capture)["observation"], "control_plane_match")
        for field, value in (("id", self.resource_id + "-replacement"), ("type", "Microsoft.Compute/disks"), ("location", "westus"), ("type", None)):
            capture = copy.deepcopy(self.capture)
            capture["resource_body"][field] = value
            with self.assertRaises(ValueError):
                AZURE.inspect(self.checklist, capture)

    def test_unknown_fields_missing_states_and_contradictory_scope_rejected(self):
        checklist = dict(self.checklist, extra="not a supported contract")
        with self.assertRaises(ValueError):
            AZURE.inspect(checklist, self.capture)
        for value in (None, True, [], ""):
            capture = copy.deepcopy(self.capture)
            capture["poll_body"]["status"] = value
            with self.assertRaises(ValueError):
                AZURE.inspect(self.checklist, capture)
        self.capture["poll_body"]["id"] = self.operation_path.replace("eastus", "westus")
        with self.assertRaises(ValueError):
            AZURE.inspect(self.checklist, self.capture)
        self.capture["poll_body"] = {"status": "Succeeded"}
        self.capture["resource_http_status"] = True
        with self.assertRaises(ValueError):
            AZURE.inspect(self.checklist, self.capture)

    def test_oversized_input_read_is_bounded(self):
        class BoundedStream(io.BytesIO):
            def read(self, size=-1):
                self.requested_size = size
                if size < 0 or size > AZURE.MAX_INPUT_BYTES + 1:
                    raise AssertionError("unbounded input read")
                return super().read(size)

        stream = BoundedStream(b" " * (AZURE.MAX_INPUT_BYTES + 2))
        with patch.object(Path, "open", return_value=stream), self.assertRaises(ValueError):
            AZURE.load_json("unused")
        self.assertEqual(stream.requested_size, AZURE.MAX_INPUT_BYTES + 1)

    def test_cli_statuses_and_invalid_json_disclose_no_evidence_or_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            checklist = Path(directory) / "checklist.json"
            capture = Path(directory) / "capture.json"
            checklist.write_text(json.dumps(self.checklist), encoding="utf-8")
            capture.write_text(json.dumps(self.capture), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(AZURE.main(["--checklist", str(checklist), "--capture", str(capture)]), 0)
            self.capture["poll_body"]["status"] = "Running"
            capture.write_text(json.dumps(self.capture), encoding="utf-8")
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(AZURE.main(["--checklist", str(checklist), "--capture", str(capture)]), 2)
            for raw in ('{"secret":"synthetic","secret":"duplicate"}', '{"secret":NaN}', "[invalid synthetic"):
                capture.write_text(raw, encoding="utf-8")
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(AZURE.main(["--checklist", str(checklist), "--capture", str(capture)]), 1)
                self.assertNotIn("synthetic", output.getvalue())
                self.assertNotIn(str(capture), output.getvalue())


if __name__ == "__main__":
    unittest.main()
