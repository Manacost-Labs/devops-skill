"""Adversarial single-hop destination, trust and disclosure regressions."""
import contextlib
import importlib.util
import io
import ipaddress
import os
import socket
import ssl
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("edge_http", ROOT / "network-edge-operations/scripts/http-path-check.py")
EDGE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EDGE)


class EdgeDepthTests(unittest.TestCase):
    def test_special_destinations_never_gain_private_override(self):
        for address in ("169.254.169.254", "fe80::1", "fd00:ec2::254", "0.0.0.0", "::", "224.0.0.1", "::ffff:169.254.169.254", "240.0.0.1"):
            with self.subTest(address=address), self.assertRaises(ValueError):
                EDGE.destination(address, True)
        self.assertEqual(EDGE.destination("10.2.3.4", True), ipaddress.ip_address("10.2.3.4"))
        with self.assertRaises(ValueError):
            EDGE.destination("::ffff:127.0.0.1", False)

    def test_mixed_dns_response_is_rejected_before_connection(self):
        answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (value, 443)) for value in ("8.8.8.8", "169.254.169.254")]
        with patch.object(EDGE.socket, "getaddrinfo", return_value=answers), patch.object(EDGE.socket, "socket") as connect:
            with self.assertRaises(ValueError):
                EDGE.request_once("https://edge.example/", allow_private=True)
            connect.assert_not_called()

    def test_credential_control_metadata_and_zone_urls_rejected(self):
        urls = ("http://user:pass@example.com/", "http://@example.com/", "http://example.com/a\r\nHost:evil", "http://example.com\\@127.0.0.1/", "http://[fe80::1%25eth0]/", "http://metadata.google.internal/", "http://instance-data./", "file:///tmp/x")
        for url in urls:
            with self.subTest(url=url), patch.object(EDGE.socket, "getaddrinfo") as lookup, self.assertRaises(ValueError):
                EDGE.resolve_target(url, True)
            lookup.assert_not_called()

    def test_numeric_override_does_not_resolve_hostname(self):
        with patch.object(EDGE.socket, "getaddrinfo", side_effect=AssertionError("unapproved DNS")):
            _, host, _, addresses = EDGE.resolve_target("https://edge.fixture.test/", True, "127.0.0.1")
            self.assertEqual(host, "edge.fixture.test")
            self.assertEqual(str(addresses[0]), "127.0.0.1")

    def test_connection_pins_first_resolution_ignores_proxy_and_stops_redirect(self):
        observed = []

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                observed.append((self.path, self.headers["Host"]))
                self.send_response(302)
                self.send_header("Location", "http://169.254.169.254/never?secret=synthetic")
                self.end_headers()

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        answers = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", server.server_port))]
        try:
            with patch.object(EDGE.socket, "getaddrinfo", side_effect=[answers, AssertionError("second resolution")]) as lookup, patch.dict(os.environ, {"HTTP_PROXY": "http://127.0.0.1:1", "HTTPS_PROXY": "http://127.0.0.1:1", "ALL_PROXY": "http://127.0.0.1:1"}):
                result = EDGE.request_once(f"http://edge.fixture.test:{server.server_port}/health?token=synthetic", allow_private=True)
            self.assertEqual(lookup.call_count, 1)
            self.assertEqual(result["status"], 302)
            self.assertNotIn("synthetic", result["location"])
            self.assertEqual(observed, [("/health?token=synthetic", f"edge.fixture.test:{server.server_port}")])
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_tls_name_and_chain_validation_are_enabled(self):
        context = ssl.create_default_context()
        context.wrap_socket = unittest.mock.Mock(side_effect=ssl.SSLCertVerificationError("fixture rejection"))
        with patch.object(EDGE.ssl, "create_default_context", return_value=context) as factory, patch.object(EDGE.socket, "socket") as numeric:
            with self.assertRaises(ssl.SSLCertVerificationError):
                EDGE.request_once("https://edge.fixture.test/", allow_private=True, connect_ip="127.0.0.1", ca_file="approved-ca.pem")
        factory.assert_called_once_with(cafile="approved-ca.pem")
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        context.wrap_socket.assert_called_once_with(numeric.return_value, server_hostname="edge.fixture.test")

    def test_cli_never_discloses_paths_queries_or_raw_connection_errors(self):
        result = {"status": 302, "location": EDGE.origin("https://user:secret@example.com/private?token=synthetic")}
        stream = io.StringIO()
        with patch("sys.argv", ["check", "https://example.com/private?token=synthetic"]), patch.object(EDGE, "request_once", return_value=result), contextlib.redirect_stdout(stream):
            self.assertEqual(EDGE.main(), 0)
        self.assertNotIn("synthetic", stream.getvalue())
        self.assertNotIn("private?", stream.getvalue())
        self.assertIn("single-hop-only", stream.getvalue())
        stream = io.StringIO()
        with patch("sys.argv", ["check", "https://example.com/"]), patch.object(EDGE, "request_once", side_effect=OSError("secret=synthetic")), contextlib.redirect_stdout(stream):
            self.assertEqual(EDGE.main(), 1)
        self.assertNotIn("synthetic", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
