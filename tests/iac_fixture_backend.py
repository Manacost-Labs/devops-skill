"""Owned loopback HTTP state/lock service for native CLI tests only.

Not a production backend: no authentication, TLS, leases, durable storage or HA.
It deliberately supports injected rejected/ambiguous state writes.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
from urllib.parse import parse_qs, urlsplit


class StateBackend:
    def __init__(self):
        self.state = None
        self.versions = []
        self.lock = None
        self.guard = threading.Lock()
        self.locked = threading.Event()
        self.grants = 0
        self.reject_writes = False
        self.commit_then_error = False
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass  # State/lock payloads never go to the CI console.

            def respond(self, code, body=b"{}"):
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def payload(self):
                size = int(self.headers.get("Content-Length", "0"))
                if size > 2 * 1024 * 1024:
                    raise ValueError("fixture request too large")
                return self.rfile.read(size)

            def do_GET(self):
                if urlsplit(self.path).path != "/state":
                    return self.respond(404)
                with owner.guard:
                    state = owner.state
                self.respond(404 if state is None else 200, state or b"{}")

            def do_LOCK(self):
                if urlsplit(self.path).path != "/lock":
                    return self.respond(404)
                incoming = json.loads(self.payload())
                with owner.guard:
                    if owner.lock is not None:
                        return self.respond(409, json.dumps(owner.lock).encode())
                    owner.lock = incoming
                    owner.grants += 1
                    owner.locked.set()
                self.respond(200)

            def do_UNLOCK(self):
                if urlsplit(self.path).path != "/lock":
                    return self.respond(404)
                incoming = json.loads(self.payload())
                with owner.guard:
                    if owner.lock is None or incoming.get("ID") != owner.lock.get("ID"):
                        return self.respond(409, json.dumps(owner.lock or {}).encode())
                    owner.lock = None
                    owner.locked.clear()
                self.respond(200)

            def do_POST(self):
                if urlsplit(self.path).path != "/state":
                    return self.respond(404)
                value = self.payload()
                json.loads(value)
                lock_id = parse_qs(urlsplit(self.path).query).get("ID", [None])[0]
                with owner.guard:
                    if owner.lock is None or lock_id != owner.lock.get("ID"):
                        return self.respond(409, json.dumps(owner.lock or {}).encode())
                    if owner.reject_writes:
                        return self.respond(500)
                    owner.state = value
                    owner.versions.append(value)
                    ambiguous = owner.commit_then_error
                self.respond(500 if ambiguous else 200)

        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.server.daemon_threads = True
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def snapshot(self):
        with self.guard:
            return self.state
