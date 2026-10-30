"""Adversarial fixture transport/disclosure and Vault freshness checks."""
import importlib.util
import io
import copy
from datetime import date, timedelta
from http.client import BadStatusLine
import socket
import tempfile
import threading
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import yaml

from vault_fixture import Client, FixtureError, MAX_RESPONSE, NoRedirect, verified_binary

ROOT = Path(__file__).resolve().parents[1]


class VaultBoundaryTests(unittest.TestCase):
    def test_rejects_nonlocal_api_intents_before_transport(self):
        client = Client(8200)
        for path in ("https://evil.test/", "//evil.test/", "/sys/health", "secret/../sys/health", "sys/health\r\nX:secret", "sys/health?token=secret"):
            with self.subTest(path=path), patch.object(client.opener, "open") as opened:
                with self.assertRaises(FixtureError):
                    client.call("GET", path, "synthetic")
                opened.assert_not_called()

    def test_proxy_environment_is_disabled_and_redirects_never_replay_credentials(self):
        with patch("vault_fixture.build_opener") as builder:
            Client(8200)
        proxy, redirects = builder.call_args.args
        self.assertEqual(proxy.proxies, {})
        self.assertIsInstance(redirects, NoRedirect)
        self.assertIsNone(redirects.redirect_request(None, None, 302, "", {}, "https://evil.test"))

    def test_api_error_body_and_transport_errors_are_not_exposed(self):
        client = Client(8200)
        error = HTTPError("secret-url", 403, "secret-message", {"secret-header": "value"}, io.BytesIO(b"secret-body"))
        with patch.object(client.opener, "open", side_effect=error):
            self.assertEqual(client.call("GET", "sys/health", "synthetic"), (403, {}))
        with patch.object(client.opener, "open", side_effect=OSError("secret-transport")):
            with self.assertRaises(FixtureError) as raised:
                client.call("GET", "sys/health", "synthetic")
        self.assertNotIn("secret", str(raised.exception))
        self.assertTrue(raised.exception.__suppress_context__)

    def test_oversized_or_invalid_response_is_a_fixed_failure(self):
        client = Client(8200)
        for body in (b"x" * (MAX_RESPONSE + 1), b"secret-invalid-json", b"[]"):
            response = Mock()
            response.__enter__ = Mock(return_value=response)
            response.__exit__ = Mock(return_value=False)
            response.read.return_value = body
            with patch.object(client.opener, "open", return_value=response):
                with self.assertRaises(FixtureError) as raised:
                    client.call("GET", "sys/health", "synthetic")
            self.assertNotIn("secret", str(raised.exception))

    def test_real_malformed_status_does_not_escape_the_disclosure_boundary(self):
        sentinel = "synthetic-sensitive-sentinel"
        with socket.socket() as server:
            server.bind(("127.0.0.1", 0))
            server.listen(1)
            server.settimeout(5)

            def respond():
                connection, _ = server.accept()
                with connection:
                    connection.settimeout(5)
                    connection.recv(4096)
                    connection.sendall((sentinel + "\r\n\r\n").encode())

            worker = threading.Thread(target=respond, daemon=True)
            worker.start()
            caught = None
            try:
                Client(server.getsockname()[1]).call("GET", "sys/health", "synthetic-token")
            except Exception as error:
                caught = error
            finally:
                worker.join(timeout=6)
            self.assertFalse(worker.is_alive())
            self.assertTrue(isinstance(caught, FixtureError))
            self.assertTrue(str(caught) == "fixture API transport or encoding failure")
            self.assertFalse(sentinel in str(caught))
            self.assertTrue(caught.__suppress_context__)

    def test_download_protocol_failure_has_no_raw_status(self):
        with tempfile.TemporaryDirectory() as directory, patch("vault_fixture.build_opener") as builder:
            builder.return_value.open.side_effect = BadStatusLine("synthetic-sensitive-sentinel")
            with self.assertRaises(FixtureError) as raised:
                verified_binary(Path(directory))
        self.assertTrue(str(raised.exception) == "official Vault fixture download or extraction failed")
        self.assertTrue(raised.exception.__suppress_context__)

    def test_vault_sources_fail_closed_when_missing_stale_or_unofficial(self):
        spec = importlib.util.spec_from_file_location("vault_validator", ROOT / "devops-platform-contracts/scripts/validate_platform.py")
        validator = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(validator)
        manifest = yaml.safe_load((ROOT / "secrets-access-operations/module.yaml").read_text(encoding="utf-8"))
        self.assertIsNone(validator.validate_freshness("secrets-access-operations", manifest))
        stale = copy.deepcopy(manifest)
        stale["source_freshness"]["last_verified"] = (date.today() - timedelta(days=184)).isoformat()
        self.assertIn("stale", validator.validate_freshness("secrets-access-operations", stale))
        unofficial = copy.deepcopy(manifest)
        unofficial["source_freshness"]["official_sources"][0] = "https://developer.hashicorp.com.attacker.test/"
        self.assertIn("non-official", validator.validate_freshness("secrets-access-operations", unofficial))
        manifest.pop("source_freshness")
        self.assertIn("must declare", validator.validate_freshness("secrets-access-operations", manifest))

    def test_native_failure_output_does_not_print_a_secret_bearing_auth_response(self):
        from smoke_vault import NativeVaultTests
        case = NativeVaultTests("test_wrapping_is_single_use_and_separate_from_grant_ttl")
        case.lab = Mock()
        case.lab.issue.return_value = {"auth": {"client_token": "synthetic-sensitive-sentinel"}}
        result = unittest.TestResult()
        case.run(result)
        self.assertEqual(len(result.failures), 1)
        self.assertNotIn("synthetic-sensitive-sentinel", result.failures[0][1])


if __name__ == "__main__":
    unittest.main()
