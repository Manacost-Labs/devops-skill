"""Source-only, owned loopback Vault fixture; never a production executor."""
from __future__ import annotations

import hashlib
from http.client import HTTPException
import io
import json
import os
from pathlib import Path
import platform
import re
import secrets
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener
from zipfile import BadZipFile, ZipFile

VERSION = "1.20.4"
# Reviewed against the official vault_1.20.4_SHA256SUMS on 2026-10-30.
ARCHIVES = {
    "linux": ("linux_amd64", "fc5fb5d01d192f1216b139fb5c6af17e3af742aaeffc289fd861920ec55f2c9c"),
    "win32": ("windows_amd64", "fcb09399aeb1e853d8d22a62043925644be07c39d50f05d55051f13430fcefeb"),
}
MAX_ARCHIVE = 300 * 1024 * 1024
MAX_EXECUTABLE = 800 * 1024 * 1024
MAX_RESPONSE = 1024 * 1024
PATH = re.compile(r"[A-Za-z0-9_/-]+(?:\?version=[0-9]+)?\Z")


class FixtureError(RuntimeError):
    """Only fixed messages may cross the fixture's evidence boundary."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def verified_binary(directory: Path) -> Path:
    if platform.machine().lower() not in {"x86_64", "amd64"} or sys.platform not in ARCHIVES:
        raise FixtureError("native Vault fixture requires Linux or Windows x86_64")
    target, digest = ARCHIVES[sys.platform]
    url = f"https://releases.hashicorp.com/vault/{VERSION}/vault_{VERSION}_{target}.zip"
    opener = build_opener(ProxyHandler({}), NoRedirect())
    try:
        with opener.open(url, timeout=90) as response:
            data = response.read(MAX_ARCHIVE + 1)
        if len(data) > MAX_ARCHIVE or hashlib.sha256(data).hexdigest() != digest:
            raise FixtureError("Vault archive size or SHA-256 mismatch")
        name = "vault.exe" if sys.platform == "win32" else "vault"
        with ZipFile(io.BytesIO(data)) as archive:
            member = archive.getinfo(name)
            if member.file_size > MAX_EXECUTABLE or member.is_dir():
                raise FixtureError("invalid Vault executable member")
            executable = archive.read(member)
        result = directory / name
        result.write_bytes(executable)
        result.chmod(0o700)
        return result
    except (OSError, HTTPError, URLError, HTTPException, BadZipFile, KeyError):
        raise FixtureError("official Vault fixture download or extraction failed") from None


class Client:
    def __init__(self, port: int):
        if type(port) is not int or not 1 <= port <= 65535:
            raise FixtureError("invalid fixture port")
        self.origin = f"http://127.0.0.1:{port}/v1/"
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def call(self, method, path, token=None, body=None, wrap=None):
        if method not in {"GET", "POST", "PUT", "DELETE"} or not isinstance(path, str) or not PATH.fullmatch(path) or path.startswith("/") or ".." in path:
            raise FixtureError("invalid fixture API intent")
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["X-Vault-Token"] = token
        if wrap is not None:
            headers["X-Vault-Wrap-TTL"] = wrap
        try:
            payload = None if body is None else json.dumps(body, allow_nan=False).encode()
            request = Request(self.origin + path, data=payload, headers=headers, method=method)
            with self.opener.open(request, timeout=5) as response:
                raw = response.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    raise FixtureError("oversized fixture API response")
                value = json.loads(raw) if raw else {}
                if not isinstance(value, dict):
                    raise FixtureError("invalid fixture API response")
                return response.status, value
        except HTTPError as error:
            # Do not include body, URL, headers, request or raw error in evidence.
            status = error.code
            error.close()
            return status, {}
        except (OSError, URLError, HTTPException, ValueError, TypeError):
            raise FixtureError("fixture API transport or encoding failure") from None


class VaultLab:
    def __init__(self, executable: Path):
        self.temp = tempfile.TemporaryDirectory(prefix="devops-vault-case-")
        self.directory = Path(self.temp.name)
        self.directory.chmod(0o700)
        self.process = None
        self.root = secrets.token_urlsafe(40)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            port = listener.getsockname()[1]
        self.client = Client(port)
        # Credentials remain in process memory. No inherited Vault/proxy/cloud
        # configuration, token-helper persistence or secret-bearing server logs.
        env = {key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP") if key in os.environ}
        env.update({"HOME": str(self.directory), "USERPROFILE": str(self.directory),
                    "VAULT_DEV_ROOT_TOKEN_ID": self.root,
                    "VAULT_DEV_LISTEN_ADDRESS": f"127.0.0.1:{port}",
                    "CHECKPOINT_DISABLE": "1"})
        try:
            self.process = subprocess.Popen(
                [str(executable), "server", "-dev", "-dev-no-store-token"],
                cwd=self.directory, env=env, stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise FixtureError("owned Vault fixture exited before readiness")
                try:
                    status, result = self.client.call("GET", "auth/token/lookup-self", self.root)
                    if status == 200 and result.get("data", {}).get("id") == self.root:
                        break
                except FixtureError:
                    pass
                time.sleep(0.1)
            else:
                raise FixtureError("owned Vault fixture readiness timed out")
        except BaseException:
            self.close()
            raise

    def close(self):
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=10)
        self.root = None
        self.temp.cleanup()

    def call(self, method, path, body=None, token=None, wrap=None):
        status, value = self.client.call(method, path, self.root if token is None else token, body, wrap)
        if status not in {200, 204}:
            raise FixtureError("fixture API operation failed")
        return value

    def issue(self, policy="reader", ttl="30s", parent=None, wrap=None):
        return self.call("POST", "auth/token/create", {
            "policies": [policy], "ttl": ttl, "explicit_max_ttl": ttl,
            "renewable": False, "no_default_policy": True,
        }, token=parent, wrap=wrap)
