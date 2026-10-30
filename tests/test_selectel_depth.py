"""Saved native Nova evidence, with Selectel scope and uncertain-effect checks."""
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
SPEC = importlib.util.spec_from_file_location("selectel_server_inspection", ROOT / "cloud-selectel/scripts/inspect-server.py")
SELECTEL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SELECTEL)


class SelectelServerInspectionTests(unittest.TestCase):
    def setUp(self):
        self.checklist = {
            "project_id": "0123456789abcdef0123456789abcdef", "pool": "ru-9", "pool_segment": "ru-9a",
            "compute_endpoint": "https://nova.fixture.example/compute/v2.1",
            "server_id": "11111111-1111-4111-8111-111111111111",
            "volume_ids": ["22222222-2222-4222-8222-222222222222"],
        }
        self.server = {
            "id": self.checklist["server_id"], "tenant_id": self.checklist["project_id"],
            "name": "nonunique-name", "status": "ACTIVE", "OS-EXT-AZ:availability_zone": "ru-9a",
            "OS-EXT-STS:task_state": None, "OS-EXT-STS:vm_state": "active", "OS-EXT-STS:power_state": 1,
            "os-extended-volumes:volumes_attached": [{"id": self.checklist["volume_ids"][0]}],
        }
        self.capture = {key: self.checklist[key] for key in ("project_id", "pool", "compute_endpoint")}
        self.capture["response"] = {"server": self.server}

    def test_exact_active_subset_cannot_prove_ownership_authority_or_health(self):
        result = SELECTEL.inspect(self.checklist, self.capture)
        self.assertEqual(result["observation"], "control_plane_match")
        for key in ("retry_authorized", "ownership_proven", "full_plan_verified", "service_health_verified"):
            self.assertIs(result[key], False)

    def test_unobserved_or_missing_uuid_never_authorizes_create_replay(self):
        self.capture["response"] = None
        result = SELECTEL.inspect(self.checklist, self.capture)
        self.assertEqual(result["observation"], "resource_unobserved")
        self.assertFalse(result["retry_authorized"])
        self.checklist["server_id"] = None
        with self.assertRaises(ValueError):
            SELECTEL.inspect(self.checklist, self.capture)

    def test_active_with_inflight_task_is_still_pending(self):
        for task in ("spawning", "rebuilding", "resize_migrating"):
            self.server["OS-EXT-STS:task_state"] = task
            self.assertEqual(SELECTEL.inspect(self.checklist, self.capture)["observation"], "pending")

    def test_build_with_missing_attachments_is_pending_not_a_failed_create(self):
        self.server.update({"status": "BUILD", "OS-EXT-STS:vm_state": "building", "OS-EXT-STS:power_state": 0})
        self.server["os-extended-volumes:volumes_attached"] = []
        result = SELECTEL.inspect(self.checklist, self.capture)
        self.assertEqual(result["observation"], "pending")
        self.assertFalse(result["retry_authorized"])

    def test_fault_error_and_crashed_state_need_attention_even_when_active(self):
        for changes in ({"status": "ERROR"}, {"fault": {"message": "synthetic-private"}},
                        {"OS-EXT-STS:vm_state": "error"}, {"OS-EXT-STS:power_state": 6}):
            capture = copy.deepcopy(self.capture)
            capture["response"]["server"].update(changes)
            result = SELECTEL.inspect(self.checklist, capture)
            self.assertEqual(result["observation"], "attention_required")
            self.assertNotIn("synthetic-private", json.dumps(result))

    def test_quiescent_nonactive_and_missing_volume_do_not_match(self):
        for changes in ({"status": "SHUTOFF"}, {"OS-EXT-STS:vm_state": "stopped"}, {"OS-EXT-STS:power_state": 4}):
            capture = copy.deepcopy(self.capture)
            capture["response"]["server"].update(changes)
            self.assertEqual(SELECTEL.inspect(self.checklist, capture)["observation"], "resource_not_active")
        self.server["os-extended-volumes:volumes_attached"] = []
        self.assertEqual(SELECTEL.inspect(self.checklist, self.capture)["observation"], "attachments_incomplete")

    def test_project_pool_endpoint_segment_and_incarnation_cannot_drift(self):
        for field, value in (("project_id", "ffffffffffffffffffffffffffffffff"), ("pool", "ru-8"),
                             ("compute_endpoint", "https://other.fixture.example/compute/v2.1")):
            capture = copy.deepcopy(self.capture)
            capture[field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                SELECTEL.inspect(self.checklist, capture)
        for field, value in (("tenant_id", "ffffffffffffffffffffffffffffffff"),
                             ("OS-EXT-AZ:availability_zone", "ru-9b"),
                             ("id", "33333333-3333-4333-8333-333333333333")):
            capture = copy.deepcopy(self.capture)
            capture["response"]["server"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                SELECTEL.inspect(self.checklist, capture)

    def test_uuid_representations_and_empty_foreign_or_duplicate_volumes(self):
        self.server["tenant_id"] = "01234567-89ab-cdef-0123-456789abcdef"
        self.assertEqual(SELECTEL.inspect(self.checklist, self.capture)["observation"], "control_plane_match")
        for volumes in ([], ["00000000-0000-0000-0000-000000000000"], self.checklist["volume_ids"] * 2):
            checklist = dict(self.checklist, volume_ids=volumes)
            with self.assertRaises(ValueError):
                SELECTEL.inspect(checklist, self.capture)
        for attachments in ([{"id": "33333333-3333-4333-8333-333333333333"}],
                            self.server["os-extended-volumes:volumes_attached"] * 2, [None], [{"id": None}]):
            self.server["os-extended-volumes:volumes_attached"] = attachments
            with self.assertRaises((ValueError, TypeError)):
                SELECTEL.inspect(self.checklist, self.capture)

    def test_native_fields_required_and_wrong_types_cannot_pass(self):
        for field in ("OS-EXT-STS:task_state", "OS-EXT-STS:power_state", "OS-EXT-STS:vm_state", "tenant_id"):
            capture = copy.deepcopy(self.capture)
            del capture["response"]["server"][field]
            with self.subTest(field=field), self.assertRaises(ValueError):
                SELECTEL.inspect(self.checklist, capture)
        for field, value in (("status", ["ACTIVE"]), ("status", "FUTURE_STATE"), ("OS-EXT-STS:power_state", True),
                             ("OS-EXT-STS:task_state", []), ("OS-EXT-STS:task_state", ""),
                             ("OS-EXT-STS:vm_state", None), ("fault", "secret"), ("fault", {})):
            capture = copy.deepcopy(self.capture)
            capture["response"]["server"][field] = value
            with self.subTest(field=field), self.assertRaises(ValueError):
                SELECTEL.inspect(self.checklist, capture)

    def test_lists_cli_fields_and_malformed_response_envelopes_rejected(self):
        for response in ({"servers": [self.server]}, {"server": self.server, "servers_links": []},
                         {"Server": self.server}, {"server": []}, {"itemNotFound": {"message": "secret"}}):
            self.capture["response"] = response
            with self.assertRaises(ValueError):
                SELECTEL.inspect(self.checklist, self.capture)
        self.capture["response"] = {"server": {"id": self.checklist["server_id"], "project_id": self.checklist["project_id"]}}
        with self.assertRaises(ValueError):
            SELECTEL.inspect(self.checklist, self.capture)

    def test_endpoint_normalization_controls_credentials_and_scope_queries_rejected(self):
        for value in ("http://nova.fixture.example/v2.1", "https://user:secret@nova.fixture.example/v2.1",
                      "https://nova.fixture.example/v2.1?token=secret", "https://nova.fixture.example/v2.1#fragment",
                      "https://nova.fixture.example/../v2.1", "https://nova.fixture.example/%2e%2e/v2.1",
                      "https://nova.fixture.example\\@other.example/v2.1", "https://nova.fixture.example/v2.1\n",
                      "https://nova.fixture.example:0/v2.1", "https://nova.fixture.example:443:443/v2.1"):
            checklist = dict(self.checklist, compute_endpoint=value)
            capture = dict(self.capture, compute_endpoint=value)
            with self.subTest(value=value), self.assertRaises(ValueError):
                SELECTEL.inspect(checklist, capture)

    def test_strict_json_bounded_read_and_unknown_checklist_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "capture.json"
            for contents in ('{"server":1,"server":2}', '{"secret":NaN}'):
                path.write_text(contents, encoding="utf-8")
                with self.assertRaises(ValueError):
                    SELECTEL.load_json(path)
        class RecordingStream(io.BytesIO):
            def read(self, size=-1):
                self.requested_size = size
                return super().read(size)

        stream = RecordingStream(b"x" * (SELECTEL.MAX_INPUT_BYTES + 100))
        with patch.object(SELECTEL.Path, "open", return_value=stream), self.assertRaises(ValueError):
            SELECTEL.load_json("unused.json")
        self.assertEqual(stream.requested_size, SELECTEL.MAX_INPUT_BYTES + 1)
        with self.assertRaises(ValueError):
            SELECTEL.inspect(dict(self.checklist, retry=True), self.capture)

    def test_cli_exit_codes_never_echo_provider_fields_or_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            checklist = Path(directory) / "checklist.json"
            capture = Path(directory) / "capture.json"
            checklist.write_text(json.dumps(self.checklist), encoding="utf-8")
            for response, expected in ((self.capture["response"], 0), (None, 2), ({"secret": "synthetic-private"}, 1)):
                self.capture["response"] = response
                capture.write_text(json.dumps(self.capture), encoding="utf-8")
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(SELECTEL.main(["--checklist", str(checklist), "--capture", str(capture)]), expected)
                self.assertNotIn("synthetic-private", output.getvalue())
                self.assertNotIn(str(capture), output.getvalue())


if __name__ == "__main__":
    unittest.main()
