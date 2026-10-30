"""Saved native GCP operation evidence: identity, errors and unresolved effects."""
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
SPEC = importlib.util.spec_from_file_location("gcp_operation_inspection", ROOT / "cloud-gcp/scripts/inspect-operation.py")
GCP = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GCP)


class GcpOperationInspectionTests(unittest.TestCase):
    def setUp(self):
        self.checklist = {"project": "fixture-project", "zone": "europe-west1-b", "operation_name": "operation-fixture",
                          "operation_id": "1234567890123456789", "request_id": "39b07683-3b41-4c8d-8bb3-cbb2c437857a",
                          "instance_name": "fixture-vm", "target_id": "2234567890123456789"}
        self.base = "https://www.googleapis.com/compute/v1/projects/fixture-project/zones/europe-west1-b"
        self.operation = {"kind": "compute#operation", "name": "operation-fixture", "id": self.checklist["operation_id"],
                          "clientOperationId": self.checklist["request_id"], "operationType": "insert", "zone": self.base,
                          "selfLink": self.base + "/operations/operation-fixture", "targetLink": self.base + "/instances/fixture-vm",
                          "targetId": self.checklist["target_id"], "status": "DONE"}
        self.instance = {"kind": "compute#instance", "id": self.checklist["target_id"], "name": "fixture-vm",
                         "selfLink": self.base + "/instances/fixture-vm", "zone": self.base, "status": "RUNNING"}
        self.capture = {"operation": self.operation, "instance": self.instance}

    def test_correlated_done_and_running_never_grant_authority_or_health(self):
        result = GCP.inspect(self.checklist, self.capture)
        self.assertEqual(result["observation"], "control_plane_match")
        for field in ("retry_authorized", "full_plan_verified", "service_health_verified"):
            self.assertIs(result[field], False)

    def test_wait_returning_pending_or_running_is_not_completion(self):
        for status in ("PENDING", "RUNNING"):
            self.operation["status"] = status
            self.assertEqual(GCP.inspect(self.checklist, self.capture)["observation"], "pending")

    def test_done_error_and_http_error_cannot_match_even_when_vm_runs(self):
        for fields in ({"error": {"errors": [{"code": "QUOTA_EXCEEDED", "message": "synthetic-private"}]}},
                       {"httpErrorStatusCode": 503}, {"httpErrorMessage": "synthetic-private"}):
            capture = copy.deepcopy(self.capture)
            capture["operation"].update(fields)
            result = GCP.inspect(self.checklist, capture)
            self.assertEqual(result["observation"], "failed")
            self.assertNotIn("synthetic-private", json.dumps(result))

    def test_done_without_independent_resource_read_remains_unobserved(self):
        self.capture["instance"] = None
        self.assertEqual(GCP.inspect(self.checklist, self.capture)["observation"], "resource_unobserved")
        self.capture["instance"] = self.instance
        for status in ("PROVISIONING", "TERMINATED", "STOPPING"):
            self.instance["status"] = status
            self.assertEqual(GCP.inspect(self.checklist, self.capture)["observation"], "resource_not_running")

    def test_recreated_resource_with_same_name_is_rejected(self):
        self.instance["id"] = "3234567890123456789"
        with self.assertRaises(ValueError):
            GCP.inspect(self.checklist, self.capture)
        self.instance["id"] = self.checklist["target_id"]
        self.operation["targetId"] = "3234567890123456789"
        with self.assertRaises(ValueError):
            GCP.inspect(self.checklist, self.capture)

    def test_operation_identity_request_and_scope_cannot_drift(self):
        for key, value in (("name", "operation-other"), ("id", "1"), ("operationType", "delete"),
                           ("clientOperationId", "c4ee78bd-0850-4df4-9f03-5ee68b0f9fd7"),
                           ("zone", self.base.replace("europe-west1-b", "europe-west1-c")),
                           ("targetLink", self.base.replace("fixture-project", "foreign-project") + "/instances/fixture-vm")):
            with self.subTest(key=key):
                capture = copy.deepcopy(self.capture)
                capture["operation"][key] = value
                with self.assertRaises(ValueError):
                    GCP.inspect(self.checklist, capture)
        self.operation["region"] = "https://www.googleapis.com/compute/v1/projects/fixture-project/regions/europe-west1"
        with self.assertRaises(ValueError):
            GCP.inspect(self.checklist, self.capture)

    def test_resource_urls_reject_ambiguous_authority_encoding_and_controls(self):
        values = (self.base.replace("www.googleapis.com", "www.googleapis.com.attacker.example"),
                  self.base.replace("https://", "http://"), self.base + "?token=synthetic", self.base + "#suffix",
                  self.base.replace("www.googleapis.com", "user@www.googleapis.com"),
                  self.base.replace("/compute/", "/\ncompute/"), self.base.replace("/projects/", "/%70rojects/"))
        for value in values:
            with self.subTest(value=value):
                capture = copy.deepcopy(self.capture)
                capture["operation"]["zone"] = value
                with self.assertRaises(ValueError):
                    GCP.inspect(self.checklist, capture)

    def test_malformed_error_and_list_envelopes_fail_closed(self):
        fields = ({"error": None}, {"error": {}}, {"error": {"errors": []}}, {"httpErrorStatusCode": True},
                  {"httpErrorStatusCode": 200}, {"httpErrorMessage": []}, {"warnings": None},
                  {"nextPageToken": "next"}, {"items": []}, {"status": ["DONE"]})
        for values in fields:
            with self.subTest(values=values):
                capture = copy.deepcopy(self.capture)
                capture["operation"].update(values)
                with self.assertRaises(ValueError):
                    GCP.inspect(self.checklist, capture)
        self.operation.update({"status": "RUNNING", "error": {"errors": [{"code": "FAILED"}]}})
        with self.assertRaises(ValueError):
            GCP.inspect(self.checklist, self.capture)

    def test_uuid_numeric_id_missing_fields_and_unknown_checklist_fields_rejected(self):
        for field, value in (("request_id", "00000000-0000-0000-0000-000000000000"), ("request_id", "not-a-uuid"),
                             ("target_id", True), ("operation_id", str(2**64)), ("unexpected", "field")):
            checklist = dict(self.checklist)
            checklist[field] = value
            with self.assertRaises(ValueError):
                GCP.inspect(checklist, self.capture)
        del self.operation["clientOperationId"]
        with self.assertRaises(ValueError):
            GCP.inspect(self.checklist, self.capture)

    def test_warning_is_retained_without_echoing_provider_text(self):
        self.operation["warnings"] = [{"code": "DISK_SIZE_LARGER_THAN_IMAGE", "message": "synthetic-private"}]
        result = GCP.inspect(self.checklist, self.capture)
        self.assertTrue(result["warnings_present"])
        self.assertNotIn("synthetic-private", json.dumps(result))

    def test_bounded_read_rejects_before_decoding_and_duplicate_fields_rejected(self):
        class BoundedStream(io.BytesIO):
            def read(self, size=-1):
                self.assertion(size)
                return super().read(size)

        stream = BoundedStream(b"x" * (GCP.MAX_INPUT_BYTES + 2))
        stream.assertion = lambda size: self.assertEqual(size, GCP.MAX_INPUT_BYTES + 1)
        with patch.object(GCP.Path, "open", return_value=stream), self.assertRaises(ValueError):
            GCP.load_json("unused.json")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplicate.json"
            for contents in ('{"id":"1","id":"2"}', '{"id":NaN}'):
                path.write_text(contents, encoding="utf-8")
                with self.assertRaises(ValueError):
                    GCP.load_json(path)

    def test_cli_exit_codes_and_failure_output_are_bounded_and_redacted(self):
        with tempfile.TemporaryDirectory() as directory:
            checklist = Path(directory) / "checklist.json"
            capture = Path(directory) / "capture.json"
            checklist.write_text(json.dumps(self.checklist), encoding="utf-8")
            for status, code in (("DONE", 0), ("RUNNING", 2)):
                self.operation["status"] = status
                capture.write_text(json.dumps(self.capture), encoding="utf-8")
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertEqual(GCP.main(["--checklist", str(checklist), "--capture", str(capture)]), code)
            capture.write_text('{"secret":"synthetic-private","secret":"duplicate"}', encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(GCP.main(["--checklist", str(checklist), "--capture", str(capture)]), 1)
            self.assertNotIn("synthetic-private", output.getvalue())
            self.assertNotIn(str(capture), output.getvalue())


if __name__ == "__main__":
    unittest.main()
