#!/usr/bin/env python3
"""Real owned CoreDNS/TLS/proxy recovery; requires disposable GitHub Linux."""
from __future__ import annotations

import hashlib
import http.client
import importlib.util
import json
import os
import re
import socket
import ssl
import sys
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import dns.flags
import dns.message
import dns.query
import dns.rcode
import dns.rdatatype
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID

from container_fixture import DockerFixture, IMAGE, OWNER, ROOT

# Official multiarch indexes resolved 2026-10-30. Print actual binary versions.
IMAGES = {
    "nginx": "nginx@sha256:0e52bd054126cdc040b1276c0af347aeb02a41b9cfe305d6094767ac30e97949",
    "caddy": "caddy@sha256:e70b164da81ef698b3ad19af799ea6086ce6d9e48ed4079eb9fe26f6fbf14ee5",
    "traefik": "traefik@sha256:1336e85aaed293bd63d005086e0dd013b04078b26aaeb1c18b26a2f928af7e65",
    "dns": "coredns/coredns@sha256:0a9d8c8ddf34347eb59aad9a8784f0710de88d6d112726d11d271f9bc6daca26",
}
HOST = "edge.fixture.test"
SPEC = importlib.util.spec_from_file_location("edge_http_native", ROOT / "network-edge-operations/scripts/http-path-check.py")
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)
UPSTREAM = r'''
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json, time
counts = {}
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        counts[self.path] = counts.get(self.path,0)+1
        if self.path == '/slow': time.sleep(4)
        self.send_response(302 if self.path == '/redirect' else 200)
        if self.path == '/redirect':
            self.send_header('Location','http://'+self.server.server_address[0]+':8080/never-follow?secret=synthetic')
        self.end_headers()
        body = counts if self.path == '/counts' else {'version':'fixture-v1','host':self.headers.get('Host'),'xff':self.headers.get('X-Forwarded-For')}
        try: self.wfile.write(json.dumps(body).encode())
        except BrokenPipeError: pass
    def log_message(self,*args): pass
ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
'''


def atomic(path, text):
    temporary = path.with_suffix(path.suffix + ".pending")
    temporary.write_text(text, encoding="utf-8")
    os.replace(temporary, path)


class EdgeFixture(DockerFixture):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine
        try:
            self.material = self.folder / "material"
            for name in ("config", "dynamic", "candidate", "certs", "dns"):
                (self.material / name).mkdir(parents=True, mode=0o700)
            self.make_pki()
            for name in (engine, "dns"):
                self.docker("pull", IMAGES[name], timeout=240)
            self.net = self.network()
            self.upstream = self.create(UPSTREAM, network=self.net, alias="upstream")
            self.docker("start", self.upstream)
            self.activate("v1", reload=False)
            self.proxy = self.create_image(engine, self.arguments(), alias="proxy")
            self.docker("start", self.proxy)
            self.wait_healthy("v1")
            address = self.address(self.proxy)
            (self.material / "dns/Corefile").write_text("fixture.test:1053 {\n file /fixture/dns/zone fixture.test\n errors\n}\n", encoding="utf-8")
            (self.material / "dns/zone").write_text(
                "$ORIGIN fixture.test.\n$TTL 30\n@ IN SOA ns.fixture.test. hostmaster.fixture.test. (1 60 60 3600 5)\n"
                "@ IN NS ns.fixture.test.\nns IN A 127.0.0.1\nedge IN A " + address + "\nalias IN CNAME edge.fixture.test.\n", encoding="utf-8")
            self.dns = self.create_image("dns", ["-conf", "/fixture/dns/Corefile"])
            self.docker("start", self.dns)
            deadline = time.monotonic() + 20
            while True:
                try:
                    self.query("edge.fixture.test", "A")
                    break
                except (OSError, dns.exception.DNSException):
                    if time.monotonic() > deadline:
                        raise
                    time.sleep(.25)
            for name, identity, arguments in ((engine, self.proxy, {"nginx": ["nginx", "-v"], "caddy": ["caddy", "version"], "traefik": ["traefik", "version"]}[engine]), ("dns", self.dns, ["/coredns", "-version"])):
                self.owned_container(identity)
                result = self.docker("exec", identity, *arguments)
                print(name + " native version: " + (result.stdout + result.stderr).strip()[:500], flush=True)
        except Exception:
            self.cleanup()
            raise

    def create_image(self, name, arguments, *, alias=None):
        image = IMAGES[name]
        image_id = self.inspect("image", image)["Id"]
        options = ["--name", self.tag + "-" + str(len(self.containers)), "--label", OWNER + "=" + self.tag,
                   "--network", self.net, "--user", f"{os.getuid()}:{os.getgid()}", "--memory", "256m",
                   "--memory-swap", "256m", "--cpus", "1", "--pids-limit", "128", "--cap-drop", "ALL",
                   "--security-opt", "no-new-privileges", "--env", "GOMAXPROCS=2", "--env", "XDG_CONFIG_HOME=/tmp/config",
                   "--env", "XDG_DATA_HOME=/tmp/data", "--mount", f"type=bind,src={self.material},dst=/fixture,readonly"]
        if alias:
            options += ["--network-alias", alias]
        options += ["--entrypoint", "/coredns" if name == "dns" else name]
        identity = self.docker("create", *options, image, *arguments).stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{64}", identity):
            raise RuntimeError("full owned edge container ID required")
        self.containers.append(identity)
        value = self.owned_container(identity)
        if value["Image"] != image_id:
            raise RuntimeError("edge image identity changed")
        return identity

    def address(self, identity):
        value = self.owned_container(identity)
        networks = list(value["NetworkSettings"]["Networks"].values())
        if len(networks) != 1 or networks[0]["NetworkID"] != self.net:
            raise RuntimeError("owned fixture network required")
        return networks[0]["IPAddress"]

    def make_pki(self):
        now = datetime.now(timezone.utc)

        def certificate(subject, issuer, public, signing, *, ca=False, expired=False):
            start, end = (datetime(2000, 1, 1, tzinfo=timezone.utc), datetime(2001, 1, 1, tzinfo=timezone.utc)) if expired else (now - timedelta(days=1), now + timedelta(days=7))
            builder = (x509.CertificateBuilder().subject_name(subject).issuer_name(issuer).public_key(public)
                       .serial_number(x509.random_serial_number()).not_valid_before(start).not_valid_after(end)
                       .add_extension(x509.BasicConstraints(ca=ca, path_length=None), critical=True)
                       .add_extension(x509.SubjectKeyIdentifier.from_public_key(public), critical=False)
                       .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(signing.public_key()), critical=False)
                       .add_extension(x509.KeyUsage(digital_signature=True, content_commitment=False, key_encipherment=False,
                           data_encipherment=False, key_agreement=False, key_cert_sign=ca, crl_sign=ca,
                           encipher_only=None, decipher_only=None), critical=True))
            if not ca:
                builder = builder.add_extension(x509.SubjectAlternativeName([x509.DNSName(HOST)]), critical=False).add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
            return builder.sign(signing, hashes.SHA256())

        def name(value):
            return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, value)])

        root_key, intermediate_key = ec.generate_private_key(ec.SECP256R1()), ec.generate_private_key(ec.SECP256R1())
        root = certificate(name("Synthetic fixture root"), name("Synthetic fixture root"), root_key.public_key(), root_key, ca=True)
        intermediate = certificate(name("Synthetic fixture intermediate"), root.subject, intermediate_key.public_key(), root_key, ca=True)
        self.ca = self.material / "root.pem"
        self.ca.write_bytes(root.public_bytes(serialization.Encoding.PEM))
        self.fingerprints = {}
        for version in ("v1", "v2", "expired", "leafonly"):
            key = ec.generate_private_key(ec.SECP256R1())
            leaf = certificate(name(HOST), intermediate.subject, key.public_key(), intermediate_key, expired=version == "expired")
            self.fingerprints[version] = leaf.fingerprint(hashes.SHA256()).hex()
            chain = leaf.public_bytes(serialization.Encoding.PEM) + (b"" if version == "leafonly" else intermediate.public_bytes(serialization.Encoding.PEM))
            (self.material / f"certs/{version}.pem").write_bytes(chain)
            key_path = self.material / f"certs/{version}.key"
            key_path.write_bytes(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
            key_path.chmod(0o600)

    def arguments(self, *, candidate=False):
        if self.engine == "nginx":
            return ["-c", "/fixture/config/nginx.conf", "-g", "daemon off;"]
        if self.engine == "caddy":
            return ["run", "--config", "/fixture/config/caddy.json"]
        return ["--entrypoints.websecure.address=:8443", "--providers.file.directory=/fixture/" + ("candidate" if candidate else "dynamic"),
                "--providers.file.watch=true", "--providers.providersThrottleDuration=100ms", "--log.level=ERROR", "--global.checknewversion=false", "--global.sendanonymoususage=false"]

    def config(self, version, *, broken=False, mismatch=False):
        cert, key = f"/fixture/certs/{version}.pem", f"/fixture/certs/{'v2' if mismatch else version}.key"
        port = 1 if broken else 8080
        if self.engine == "nginx":
            return f'''pid /tmp/nginx.pid;
error_log /dev/stderr warn;
events {{ worker_connections 128; }}
http {{ access_log off; client_body_temp_path /tmp/client; proxy_temp_path /tmp/proxy;
 fastcgi_temp_path /tmp/fastcgi; uwsgi_temp_path /tmp/uwsgi; scgi_temp_path /tmp/scgi;
 ssl_certificate {cert}; ssl_certificate_key {key};
 server {{ listen 8443 ssl default_server; server_name _; return 421; }}
 server {{ listen 8443 ssl; server_name {HOST}; location / {{
 proxy_pass http://upstream:{port}; proxy_set_header Host $host;
 proxy_set_header X-Forwarded-For $remote_addr; proxy_set_header X-Forwarded-Proto $scheme;
 proxy_connect_timeout 1s; proxy_read_timeout 1s; proxy_next_upstream off;
 }} }} }}
'''
        if self.engine == "caddy":
            return json.dumps({"admin": {"listen": "127.0.0.1:2019"}, "logging": {"logs": {"default": {"level": "ERROR"}}},
                "apps": {"tls": {"certificates": {"load_files": [{"certificate": cert, "key": key}]}},
                    "http": {"servers": {"fixture": {"listen": [":8443"], "automatic_https": {"disable": True},
                        "tls_connection_policies": [{}], "routes": [{"match": [{"host": [HOST]}], "handle": [{"handler": "reverse_proxy",
                            "upstreams": [{"dial": f"upstream:{port}"}], "transport": {"protocol": "http", "response_header_timeout": "1s", "dial_timeout": "1s"}}]}]}}}}})
        return json.dumps({"http": {"routers": {"fixture": {"rule": f"Host(`{HOST}`)", "entryPoints": ["websecure"], "service": "fixture", "tls": {}}},
            "services": {"fixture": {"loadBalancer": {"servers": [{"url": f"http://upstream:{port}"}], "serversTransport": "fixture"}}},
            "serversTransports": {"fixture": {"forwardingTimeouts": {"dialTimeout": "1s", "responseHeaderTimeout": "1s"}}}},
            "tls": {"certificates": [{"certFile": cert, "keyFile": key}]}})

    def activate(self, version, *, broken=False, reload=True):
        suffix = {"nginx": "config/nginx.conf", "caddy": "config/caddy.json", "traefik": "dynamic/routes.yaml"}[self.engine]
        atomic(self.material / suffix, self.config(version, broken=broken))
        if reload and self.engine != "traefik":
            self.owned_container(self.proxy)
            validation = ["nginx", "-t", "-c", "/fixture/config/nginx.conf"] if self.engine == "nginx" else ["caddy", "validate", "--config", "/fixture/config/caddy.json"]
            self.docker("exec", self.proxy, *validation)
            arguments = ["nginx", "-s", "reload", "-c", "/fixture/config/nginx.conf"] if self.engine == "nginx" else ["caddy", "reload", "--config", "/fixture/config/caddy.json", "--force"]
            self.docker("exec", self.proxy, *arguments)

    def probe(self, path="/", *, hostname=HOST, host_header=None, trust=True, headers=None, identity=None):
        identity = identity or self.proxy
        context = ssl.create_default_context(cafile=str(self.ca)) if trust else ssl.create_default_context()
        with socket.create_connection((self.address(identity), 8443), timeout=5) as raw:
            with context.wrap_socket(raw, server_hostname=hostname) as transport:
                fingerprint = hashlib.sha256(transport.getpeercert(binary_form=True)).hexdigest()
                request_headers = {"Host": host_header or HOST, "Connection": "close", **(headers or {})}
                message = f"GET {path} HTTP/1.1\r\n" + "".join(f"{key}: {value}\r\n" for key, value in request_headers.items()) + "\r\n"
                transport.sendall(message.encode("ascii"))
                response = http.client.HTTPResponse(transport)
                response.begin()
                return response.status, response.read(16384), fingerprint

    def wait_healthy(self, version):
        deadline = time.monotonic() + 25
        observation = "not observed"
        while True:
            try:
                status, body, fingerprint = self.probe()
                if status == 200 and json.loads(body)["version"] == "fixture-v1" and fingerprint == self.fingerprints[version]:
                    return
                observation = f"status={status} fingerprint={fingerprint}"
            except (OSError, ValueError, http.client.HTTPException) as error:
                observation = type(error).__name__ + ": " + str(error)[:400]
            if time.monotonic() > deadline:
                logs = self.docker("logs", "--tail", "15", self.proxy)
                raise AssertionError("native proxy failed health/fingerprint: " + observation + " " + (logs.stdout + logs.stderr)[-2000:])
            time.sleep(.25)

    def wait_status(self, status):
        deadline = time.monotonic() + 25
        while True:
            observed, _, _ = self.probe()
            if observed == status:
                return
            if time.monotonic() > deadline:
                raise AssertionError(f"expected {status}; observed {observed}")
            time.sleep(.25)

    def query(self, name, kind, *, tcp=False):
        query = dns.message.make_query(name, kind)
        return (dns.query.tcp if tcp else dns.query.udp)(query, self.address(self.dns), port=1053, timeout=3)


class EdgeSmoke(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = EdgeFixture(ENGINE)

    @classmethod
    def tearDownClass(cls):
        cls.fixture.cleanup()

    def setUp(self):
        self.fixture.activate("v1")
        self.fixture.wait_healthy("v1")

    def test_authoritative_dns_tcp_udp_and_negative_answers(self):
        fixture = self.fixture
        for tcp in (False, True):
            answer = fixture.query(HOST, "A", tcp=tcp)
            self.assertTrue(answer.flags & dns.flags.AA)
            self.assertEqual(answer.rcode(), dns.rcode.NOERROR)
            self.assertEqual(answer.answer[0][0].address, fixture.address(fixture.proxy))
            self.assertEqual(answer.answer[0].ttl, 30)
            alias = fixture.query("alias.fixture.test", "A", tcp=tcp)
            self.assertEqual(str(alias.answer[0][0].target), HOST + ".")
            self.assertEqual(alias.answer[-1][0].address, fixture.address(fixture.proxy))
            nodata = fixture.query(HOST, "AAAA", tcp=tcp)
            self.assertEqual(nodata.rcode(), dns.rcode.NOERROR)
            self.assertFalse(nodata.answer)
            missing = fixture.query("absent.fixture.test", "A", tcp=tcp)
            self.assertEqual(missing.rcode(), dns.rcode.NXDOMAIN)
            self.assertEqual(missing.authority[0].rdtype, dns.rdatatype.SOA)
            self.assertEqual(missing.authority[0][0].minimum, 5)
        self.assertEqual(fixture.probe()[0], 200)

    def test_strict_chain_sni_route_and_upstream_identity(self):
        status, body, fingerprint = self.fixture.probe()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["version"], "fixture-v1")
        self.assertEqual(json.loads(body)["host"], HOST)
        self.assertEqual(fingerprint, self.fixture.fingerprints["v1"])

    def test_helper_with_private_trust_preserves_hostname(self):
        result = HELPER.request_once(f"https://{HOST}:8443/", allow_private=True, connect_ip=self.fixture.address(self.fixture.proxy), ca_file=str(self.fixture.ca))
        self.assertEqual(result["status"], 200)

    def test_unknown_ca_rejected(self):
        with self.assertRaises(ssl.SSLCertVerificationError):
            self.fixture.probe(trust=False)

    def test_wrong_hostname_rejected(self):
        with self.assertRaises(ssl.SSLError):
            self.fixture.probe(hostname="wrong.fixture.test")

    def assert_bad_pair_rejected(self, version, codes):
        self.fixture.activate(version)
        deadline = time.monotonic() + 25
        while True:
            try:
                self.fixture.probe()
            except ssl.SSLCertVerificationError as error:
                if error.verify_code in codes:
                    return
                raise
            if time.monotonic() > deadline:
                self.fail("invalid certificate still accepted")
            time.sleep(.25)

    def test_missing_intermediate_rejected(self):
        self.assert_bad_pair_rejected("leafonly", {20, 21})

    def test_expired_leaf_rejected(self):
        self.assert_bad_pair_rejected("expired", {10})

    def test_invalid_pair_preflight_preserves_live_service(self):
        fixture = self.fixture
        extension = {"nginx": "conf", "caddy": "json", "traefik": "yaml"}[ENGINE]
        path = fixture.material / f"candidate/invalid.{extension}"
        atomic(path, fixture.config("v1", mismatch=True))
        if ENGINE in {"nginx", "caddy"}:
            arguments = ["nginx", "-t", "-c", "/fixture/candidate/invalid.conf"] if ENGINE == "nginx" else ["caddy", "validate", "--config", "/fixture/candidate/invalid.json"]
            fixture.owned_container(fixture.proxy)
            result = fixture.docker("exec", fixture.proxy, *arguments, expected=None)
            self.assertNotEqual(result.returncode, 0)
            self.assertRegex((result.stdout + result.stderr).lower(), "key.*match|match.*key")
        else:
            candidate = fixture.create_image("traefik", fixture.arguments(candidate=True))
            fixture.docker("start", candidate)
            deadline = time.monotonic() + 20
            while True:
                logs = fixture.docker("logs", "--tail", "20", candidate)
                if re.search("key.*match|match.*key", (logs.stdout + logs.stderr).lower()):
                    break
                if time.monotonic() > deadline:
                    self.fail("actual Traefik did not reject mismatched pair")
                time.sleep(.25)
            with self.assertRaises(ssl.SSLError):
                fixture.probe(identity=candidate)
            fixture.owned_container(candidate)
            fixture.docker("stop", "--time", "2", candidate)
        fixture.wait_healthy("v1")

    def test_certificate_rotation_without_process_restart(self):
        before = self.fixture.owned_container(self.fixture.proxy)["State"]["Pid"]
        self.fixture.activate("v2")
        self.fixture.wait_healthy("v2")
        self.assertEqual(before, self.fixture.owned_container(self.fixture.proxy)["State"]["Pid"])
        self.assertNotEqual(self.fixture.fingerprints["v1"], self.fixture.fingerprints["v2"])

    def test_valid_but_broken_upstream_and_actual_recovery(self):
        self.fixture.activate("v1", broken=True)
        self.fixture.wait_status(502)
        self.fixture.activate("v1")
        self.fixture.wait_healthy("v1")

    def test_slow_upstream_produces_gateway_timeout(self):
        started = time.monotonic()
        self.assertEqual(self.fixture.probe("/slow")[0], 504)
        self.assertLess(time.monotonic() - started, 4)

    def test_unmatched_host_never_reaches_upstream(self):
        status, body, _ = self.fixture.probe(host_header="wrong.fixture.test")
        self.assertIn(status, {404, 421})
        self.assertNotIn(b"fixture-v1", body)

    def test_client_cannot_spoof_forwarded_address(self):
        _, body, _ = self.fixture.probe(headers={"X-Forwarded-For": "203.0.113.99"})
        self.assertNotIn("203.0.113.99", json.loads(body)["xff"] or "")

    def test_helper_stops_redirect_without_disclosing_query(self):
        result = HELPER.request_once(f"https://{HOST}:8443/redirect", allow_private=True, connect_ip=self.fixture.address(self.fixture.proxy), ca_file=str(self.fixture.ca))
        self.assertEqual(result["status"], 302)
        self.assertNotIn("synthetic", result["location"])
        _, body, _ = self.fixture.probe("/counts")
        self.assertFalse(any(key.startswith("/never-follow") for key in json.loads(body)))


if __name__ == "__main__":
    ENGINE = sys.argv.pop(1) if len(sys.argv) > 1 else ""
    if ENGINE not in {"nginx", "caddy", "traefik"}:
        raise SystemExit("explicit nginx/caddy/traefik fixture required")
    unittest.main()
