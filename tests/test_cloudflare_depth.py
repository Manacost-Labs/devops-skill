from __future__ import annotations

import copy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("cloudflare_guard", ROOT / "cloudflare-operations/scripts/state-guard.py")
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)
CAPTURE_SPEC = importlib.util.spec_from_file_location("cloudflare_capture", ROOT / "cloudflare-operations/scripts/capture-readonly.py")
CAPTURE = importlib.util.module_from_spec(CAPTURE_SPEC)
CAPTURE_SPEC.loader.exec_module(CAPTURE)


def snapshot(product="access"):
    configurations = {
        "access": {"decision": "allow", "include": [{"email_domain": {"domain": "fixture.invalid"}}], "require": [{"group": {"id": "test-group"}}], "exclude": []},
        "waf": {"phase": "http_request_firewall_custom", "rules": [{"id": "a", "expression": "http.request.uri.path eq \"/drill\"", "action": "block"}, {"id": "b", "expression": "true", "action": "log"}]},
        "tunnel": {"ingress": [{"hostname": "drill.fixture.invalid", "service": "http://127.0.0.1:8080"}, {"service": "http_status:404"}]},
        "workers": {"versions": [{"version_id": "v1", "percentage": 100}], "bindings": [{"type": "kv_namespace", "name": "TEST", "namespace_id": "fixture"}]},
    }
    return {"schema_version": 1, "product": product, "account_id": "a" * 32, "zone_id": "b" * 32, "objects": [{"resource": product, "id": "fixture-object", "revision": "1", "configuration": configurations[product]}]}


class StateGuardTests(unittest.TestCase):
    def test_all_products_reconcile_lost_response_without_retry_authority(self):
        for product in sorted(GUARD.PRODUCTS):
            with self.subTest(product=product):
                before = snapshot(product)
                intended = copy.deepcopy(before)
                intended["objects"][0]["configuration"]["drill_marker"] = "candidate"
                observed = copy.deepcopy(intended)
                observed["objects"][0]["revision"] = "2"
                self.assertEqual(GUARD.preflight(before, observed)["decision"], "blocked_drift")
                result = GUARD.reconcile(before, intended, observed)
                self.assertEqual(result["decision"], "intended_configuration")
                self.assertFalse(result["retry_safe"])
                self.assertFalse(result["authorizes_write"])
                self.assertFalse(result["provider_verified"])

    def test_revision_only_drift_blocks_preflight_and_ambiguous_before_state(self):
        before = snapshot()
        current = copy.deepcopy(before)
        current["objects"][0]["revision"] = "2"
        desired = copy.deepcopy(before)
        desired["objects"][0]["configuration"]["decision"] = "deny"
        self.assertEqual(GUARD.preflight(before, current)["decision"], "blocked_drift")
        self.assertEqual(GUARD.reconcile(before, desired, current)["decision"], "blocked_conflict")

    def test_unchanged_object_with_new_revision_blocks_aggregate(self):
        before = snapshot()
        second = copy.deepcopy(before["objects"][0]); second["id"] = "second"; before["objects"].append(second)
        desired = copy.deepcopy(before); desired["objects"][0]["configuration"]["decision"] = "deny"
        current = copy.deepcopy(desired); current["objects"][1]["revision"] = "8"
        self.assertEqual(GUARD.reconcile(before, desired, current)["decision"], "blocked_conflict")

    def test_partial_success_and_third_party_rollback_drift(self):
        before = snapshot()
        second = copy.deepcopy(before["objects"][0]); second["id"] = "fixture-second"
        before["objects"].append(second)
        desired = copy.deepcopy(before)
        for obj in desired["objects"]:
            obj["configuration"]["decision"] = "deny"
        current = copy.deepcopy(before)
        current["objects"][0] = copy.deepcopy(desired["objects"][0])
        current["objects"][0]["revision"] = "2"
        self.assertEqual(GUARD.reconcile(before, desired, current)["decision"], "partial")
        applied = copy.deepcopy(current)
        current["objects"][0]["configuration"]["unrelated_owner_change"] = True
        self.assertEqual(GUARD.preflight(applied, current)["decision"], "blocked_drift")
        self.assertEqual(GUARD.reconcile(before, desired, current)["decision"], "blocked_conflict")

    def test_policy_rule_ingress_and_split_order_are_not_sorted_away(self):
        for product, key in (("waf", "rules"), ("tunnel", "ingress")):
            old = snapshot(product)
            current = copy.deepcopy(old)
            current["objects"][0]["configuration"][key].reverse()
            self.assertEqual(GUARD.preflight(old, current)["decision"], "blocked_drift")
        old = snapshot()
        current = copy.deepcopy(old)
        current["objects"][0]["configuration"]["include"] = [{"everyone": {}}]
        self.assertEqual(GUARD.preflight(old, current)["decision"], "blocked_drift")

    def test_scope_and_object_inventory_mismatch_are_invalid(self):
        for mutate in (lambda x: x.update(account_id="c" * 32), lambda x: x.update(zone_id="c" * 32), lambda x: x.update(product="tunnel"), lambda x: x["objects"][0].update(id="other-object")):
            old = snapshot(); current = copy.deepcopy(old); mutate(current)
            with self.assertRaises(ValueError):
                GUARD.preflight(old, current)

    def test_object_inventory_order_is_immaterial(self):
        old = snapshot()
        obj = copy.deepcopy(old["objects"][0]); obj["id"] = "second"; old["objects"].append(obj)
        current = copy.deepcopy(old); current["objects"].reverse()
        self.assertEqual(GUARD.preflight(old, current)["decision"], "snapshot_match")

    def test_unknown_fields_duplicate_objects_secrets_and_nonfinite_rejected(self):
        for mutate in (lambda x: x.update(extra=True), lambda x: x.update(schema_version=True), lambda x: x["objects"].append(copy.deepcopy(x["objects"][0])), lambda x: x["objects"][0]["configuration"].update(token="synthetic-do-not-print"), lambda x: x["objects"][0]["configuration"].update(value=float("nan")), lambda x: x["objects"][0].update(revision="\x1b[31m")):
            data = snapshot(); mutate(data)
            with self.assertRaises(ValueError):
                GUARD.validate(data)

    def test_cli_boundaries_suppress_raw_input(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "snapshot.json"
            for raw in ('{"synthetic-private-marker":1,"synthetic-private-marker":2}', '{"value":NaN}', '[' * 1500, 'x' * (GUARD.LIMIT + 1)):
                source.write_text(raw, encoding="utf-8")
                result = subprocess.run([sys.executable, str(Path(GUARD.__file__)), "preflight", str(source), str(source)], capture_output=True, text=True)
                self.assertEqual(result.returncode, 2)
                self.assertNotIn("synthetic-private-marker", result.stdout + result.stderr)
                self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_rollback_match_is_not_rollback_authorization(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "snapshot.json"; source.write_text(json.dumps(snapshot()), encoding="utf-8")
            result = subprocess.run([sys.executable, str(Path(GUARD.__file__)), "rollback-preflight", str(source), str(source)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0)
            report = json.loads(result.stdout)
            self.assertEqual(report["decision"], "snapshot_match_requires_recovery_review")
            self.assertFalse(report["authorizes_write"])


class CaptureTests(unittest.TestCase):
    def test_endpoint_rejects_path_injection_before_network(self):
        for resource in ("../other", "a/b", "a?token=value", "a%2fb", "a\r\nHost:evil"):
            with self.subTest(resource=resource), patch.object(CAPTURE.urllib.request, "build_opener") as build, self.assertRaises(ValueError):
                CAPTURE.capture("worker-deployments", "a" * 32, "b" * 32, resource, "synthetic")
            build.assert_not_called()

    def test_all_products_get_only_fixed_api_after_zone_binding(self):
        for kind in sorted(CAPTURE.KINDS):
            calls = []
            product_result = {
                "access-app": {"id": "fixture", "type": "self_hosted"},
                "access-policy": {"id": "fixture", "decision": "allow", "include": []},
                "waf-ruleset": {"id": "fixture", "phase": "http_request_firewall_custom", "version": "2", "rules": []},
                "tunnel-config": {"tunnel_id": "fixture", "version": 2, "config": {}},
                "worker-deployments": {"deployments": [{"id": "deployment2", "versions": [{"version_id": "v2", "percentage": 100}]}]},
            }[kind]
            class Response:
                status = 200
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def read(self, limit):
                    result = {"id": "b" * 32, "account": {"id": "a" * 32}} if len(calls) == 1 else product_result
                    return json.dumps({"success": True, "errors": [], "result": result}).encode()
            class Opener:
                def open(self, request, timeout):
                    calls.append(request)
                    self_test.assertEqual(timeout, 15)
                    return Response()
            self_test = self
            result = CAPTURE.capture(kind, "a" * 32, "b" * 32, "fixture", "synthetic", Opener())
            self.assertEqual(len(calls), 2)
            self.assertTrue(all(req.get_method() == "GET" and req.full_url.startswith(CAPTURE.API + "/") for req in calls))
            self.assertEqual(result["coverage"], "one_api_response_only")
            self.assertFalse(result["provider_behavior_verified"])

    def test_wrong_zone_owner_stops_before_product_get(self):
        with patch.object(CAPTURE, "read_once", return_value=({"id": "b" * 32, "account": {"id": "c" * 32}}, "sha256:fixture", None)) as read, self.assertRaises(ValueError):
            CAPTURE.capture("tunnel-config", "a" * 32, "b" * 32, "fixture", "synthetic", object())
        self.assertEqual(read.call_count, 1)

    def test_redirect_refused_and_ambient_proxy_disabled(self):
        with self.assertRaises(ValueError):
            CAPTURE.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.invalid/")
        with patch.object(CAPTURE.urllib.request, "build_opener") as build, patch.object(CAPTURE, "read_once", side_effect=ValueError("stop")), self.assertRaises(ValueError):
            CAPTURE.capture("access-app", "a" * 32, "b" * 32, "fixture", "synthetic")
        proxy, redirect = build.call_args.args
        self.assertEqual(proxy.proxies, {})
        self.assertIsInstance(redirect, CAPTURE.NoRedirect)

    def test_wrong_returned_identity_and_product_schema_are_rejected(self):
        bad = {
            "access-app": [None, [], {"id": "other", "type": "self_hosted"}, {"id": "fixture"}],
            "access-policy": [{"id": "other", "decision": "allow", "include": []}, {"id": "fixture", "decision": "allow", "include": None}],
            "waf-ruleset": [{"id": "other", "phase": "p", "version": "1", "rules": []}, {"id": "fixture", "phase": "p", "rules": []}],
            "tunnel-config": [{"tunnel_id": "other", "version": 1, "config": {}}, {"tunnel_id": "fixture", "version": True, "config": {}}],
            "worker-deployments": [[], {"deployments": None}, {"deployments": [{"id": "d", "versions": []}]}, {"deployments": [{"id": "d", "versions": [{"version_id": "v", "percentage": 90}]}]}],
        }
        for kind, cases in bad.items():
            for result in cases:
                with self.subTest(kind=kind, result=result), self.assertRaises(ValueError):
                    CAPTURE.validate_result(kind, "fixture", result)

    def test_invalid_response_no_retry_no_raw_secret_output(self):
        for payload in ({"success": False, "errors": [{"message": "synthetic-private-marker"}], "result": {}}, {"success": True, "result": {"token": "synthetic-private-marker"}}):
            class Response:
                status = 200
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def read(self, limit): return json.dumps(payload).encode()
            with patch.object(CAPTURE.urllib.request.OpenerDirector, "open", return_value=Response()) as call, self.assertRaises(ValueError):
                CAPTURE.read_once(CAPTURE.urllib.request.build_opener(), "/zones/" + "b" * 32, "synthetic")
            self.assertEqual(call.call_count, 1)

    def test_pagination_metadata_cannot_smuggle_credentials_or_nonfinite_values(self):
        for pagination in ({"token": "synthetic-private-marker"}, {"count": float("inf")}, ["unexpected"]):
            class Response:
                status = 200
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def read(self, limit):
                    return json.dumps({"success": True, "errors": [], "result": {}, "result_info": pagination}).encode()
            with patch.object(CAPTURE.urllib.request.OpenerDirector, "open", return_value=Response()), self.assertRaises(ValueError):
                CAPTURE.read_once(CAPTURE.urllib.request.build_opener(), "/zones/" + "b" * 32, "synthetic")


class LoopbackTransportTests(unittest.TestCase):
    def serve(self, handler):
        server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 3)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def test_actual_get_transport_and_account_binding(self):
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append((self.command, self.path))
                result = {"id": "b" * 32, "account": {"id": "a" * 32}} if self.path == "/zones/" + "b" * 32 else {"id": "fixture", "phase": "http_request_firewall_custom", "version": "2", "rules": []}
                payload = json.dumps({"success": True, "errors": [], "result": result}).encode()
                self.send_response(200); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
            def log_message(self, *args): pass
        server = self.serve(Handler)
        with patch.object(CAPTURE, "API", f"http://127.0.0.1:{server.server_port}"), patch.dict(CAPTURE.os.environ, {"HTTP_PROXY": "http://127.0.0.1:1", "HTTPS_PROXY": "http://127.0.0.1:1"}):
            result = CAPTURE.capture("waf-ruleset", "a" * 32, "b" * 32, "fixture", "synthetic-loopback-only")
        self.assertEqual(seen, [("GET", "/zones/" + "b" * 32), ("GET", "/zones/" + "b" * 32 + "/rulesets/fixture")])
        self.assertEqual(result["result"]["version"], "2")
        self.assertFalse(result["provider_behavior_verified"])

    def test_actual_redirect_never_replays_credential_to_destination(self):
        seen = []
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                seen.append(self.path)
                self.send_response(302); self.send_header("Location", "/credential-destination"); self.send_header("Content-Length", "0"); self.end_headers()
            def log_message(self, *args): pass
        server = self.serve(Handler)
        opener = CAPTURE.urllib.request.build_opener(CAPTURE.urllib.request.ProxyHandler({}), CAPTURE.NoRedirect())
        with patch.object(CAPTURE, "API", f"http://127.0.0.1:{server.server_port}"), self.assertRaises(ValueError):
            CAPTURE.read_once(opener, "/zones/" + "b" * 32, "synthetic-loopback-only")
        self.assertEqual(len(seen), 1)

    def test_actual_duplicate_nonfinite_and_oversize_body_are_refused(self):
        bodies = [b'{"success":true,"result":{},"result":{"id":"other"}}', b'{"success":true,"result":{"value":NaN}}', b"x" * (GUARD.LIMIT + 1)]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                payload = bodies.pop(0)
                self.send_response(200); self.send_header("Content-Length", str(len(payload))); self.end_headers(); self.wfile.write(payload)
            def log_message(self, *args): pass
        server = self.serve(Handler)
        opener = CAPTURE.urllib.request.build_opener(CAPTURE.urllib.request.ProxyHandler({}), CAPTURE.NoRedirect())
        with patch.object(CAPTURE, "API", f"http://127.0.0.1:{server.server_port}"):
            for _ in range(3):
                with self.assertRaises(ValueError):
                    CAPTURE.read_once(opener, "/zones/" + "b" * 32, "synthetic-loopback-only")
        self.assertFalse(bodies)

    def test_malformed_status_and_truncated_chunks_have_private_structured_cli_error(self):
        responses = [b"synthetic-private-marker\r\n\r\n", b"HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\n\r\n10\r\nshort"]
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.wfile.write(responses.pop(0))
                self.wfile.flush()
                self.close_connection = True
            def log_message(self, *args): pass
        server = self.serve(Handler)
        with tempfile.TemporaryDirectory() as directory, patch.object(CAPTURE, "API", f"http://127.0.0.1:{server.server_port}"), patch.dict(CAPTURE.os.environ, {"CLOUDFLARE_API_TOKEN": "synthetic-loopback-only"}):
            for index in range(2):
                output = Path(directory) / f"result{index}.json"
                stdout, stderr = io.StringIO(), io.StringIO()
                with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                    code = CAPTURE.main(["--kind", "waf-ruleset", "--account-id", "a" * 32, "--zone-id", "b" * 32, "--resource-id", "fixture", "--output", str(output)])
                self.assertEqual(code, 2)
                self.assertEqual(json.loads(stdout.getvalue())["status"], "blocked")
                self.assertNotIn("synthetic-private-marker", stdout.getvalue() + stderr.getvalue())
                self.assertNotIn("Traceback", stdout.getvalue() + stderr.getvalue())
                self.assertFalse(output.exists())
        self.assertFalse(responses)


if __name__ == "__main__":
    unittest.main()
