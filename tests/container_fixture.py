"""Owned disposable GitHub Linux runner resources; import has no side effects."""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Official Python multiarch index resolved 2026-10-29; synthetic data only.
IMAGE = "python:3.13-alpine@sha256:7984cf56ceaddebe4fefeb75d64000b9f45d8b77b11a09b24524da6cdc3af0c8"
OWNER = "devops.fixture.owner"
APP = r"""
import json, pathlib, sqlite3, sys
mode=sys.argv[1]
data=pathlib.Path('/data/db.sqlite')
def connect(path):
    return sqlite3.connect('file:'+str(path)+'?mode=ro',uri=True)
try:
    if mode=='init':
        with sqlite3.connect(data) as db:
            db.execute('CREATE TABLE records(id INTEGER PRIMARY KEY, value TEXT NOT NULL)')
            db.execute("INSERT INTO records VALUES(1,'before')")
    elif mode=='backup':
        with connect(data) as source, sqlite3.connect('/backup/pre.sqlite') as target:
            source.backup(target)
    elif mode=='migrate':
        with sqlite3.connect(data) as db:
            db.execute('ALTER TABLE records RENAME COLUMN value TO payload')
    elif mode=='write':
        with sqlite3.connect(data) as db:
            db.execute("INSERT INTO records VALUES(2,'after')")
    elif mode=='repair':
        with sqlite3.connect(data) as db:
            db.execute('ALTER TABLE records ADD COLUMN value TEXT')
            db.execute('UPDATE records SET value=payload')
    elif mode=='restore':
        with connect('/backup/pre.sqlite') as source, sqlite3.connect('/restore/db.sqlite') as target:
            source.backup(target)
    elif mode in ('old','new','restored'):
        column='payload' if mode=='new' else 'value'
        with connect('/restore/db.sqlite' if mode=='restored' else data) as db:
            rows=db.execute('SELECT id,'+column+' FROM records ORDER BY id').fetchall()
        print(json.dumps(rows))
    else:
        raise RuntimeError('unknown synthetic mode')
except sqlite3.OperationalError:
    print('incompatible_or_unavailable_schema')
    sys.exit(20)
"""
HTTP = """
from http.server import BaseHTTPRequestHandler, HTTPServer
import sys
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200); self.end_headers(); self.wfile.write(b'fixture-ok')
    def log_message(self,*args): pass
HTTPServer((sys.argv[1],8080),Handler).serve_forever()
"""
REQUEST = """
import socket, sys, time, urllib.request
host=sys.argv[1]
resolved=False
for _ in range(6):
    try:
        socket.getaddrinfo(host,8080); resolved=True
        assert urllib.request.urlopen('http://'+host+':8080',timeout=2).read()==b'fixture-ok'
        print('request-ok'); sys.exit(0)
    except (OSError, AssertionError): time.sleep(.5)
sys.exit(23 if resolved else 24)
"""


def command(argv, *, environment=None, timeout=120, input=None, expected=0):
    result = subprocess.run(argv, env=environment, input=input, capture_output=True, text=True, timeout=timeout)
    if expected is not None and result.returncode != expected:
        raise RuntimeError("fixture command failed: "+str(argv[:3])+" "+result.stderr[-1500:])
    return result


def fixture_environment(original, folder):
    environment = {key: value for key, value in original.items()
                   if not key.startswith(("DOCKER_", "KIND_")) and key != "KUBECONFIG"}
    environment["DOCKER_HOST"] = "unix:///var/run/docker.sock"
    environment["DOCKER_CONFIG"] = str(folder/"docker-config")
    environment["KUBECONFIG"] = str(folder/"kubeconfig")
    environment["KIND_EXPERIMENTAL_PROVIDER"] = "docker"
    return environment


class DockerFixture:
    def __init__(self):
        if (os.name != "posix" or os.environ.get("GITHUB_ACTIONS") != "true"
                or os.environ.get("RUNNER_OS") != "Linux" or os.environ.get("RUNNER_ENVIRONMENT") != "github-hosted"):
            raise RuntimeError("disposable GitHub-hosted Linux runner required")
        parent = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
        if not stat.S_ISSOCK(Path("/var/run/docker.sock").stat().st_mode):
            raise RuntimeError("local Docker socket required")
        self.folder = Path(tempfile.mkdtemp(prefix="devops-container-", dir=parent))
        if self.folder.parent.resolve() != parent:
            raise RuntimeError("fixture path escaped runner workspace")
        self.tag = "devops-" + uuid.uuid4().hex
        self.environment = fixture_environment(os.environ, self.folder)
        (self.folder/"docker-config").mkdir(mode=0o700)
        self.containers, self.networks, self.volumes = [], [], []
        self.image_tag = None
        self.daemon_id = None
        try:
            info = json.loads(self.docker("info", "--format", "{{json .}}").stdout)
            if info.get("OSType") != "linux" or not info.get("ID"):
                raise RuntimeError("Linux daemon identity required")
            self.daemon_id = info["ID"]
            self.docker("pull", IMAGE, timeout=240)
            self.image_id = self.inspect("image", IMAGE)["Id"]
        except Exception:
            self.cleanup_files()
            raise

    def docker(self, *args, **kwargs):
        if self.daemon_id is not None and args[0] != "info":
            self.check_daemon()
        return command(["docker", "--host", "unix:///var/run/docker.sock", "--config",
                        str(self.folder/"docker-config"), *args], environment=self.environment, **kwargs)

    def inspect(self, kind, identity):
        items = json.loads(self.docker(kind, "inspect", identity).stdout)
        if not isinstance(items, list) or len(items) != 1:
            raise RuntimeError("exact fixture object required")
        return items[0]

    def check_daemon(self):
        current = json.loads(self.docker("info", "--format", "{{json .}}").stdout)
        if current.get("ID") != self.daemon_id or current.get("OSType") != "linux":
            raise RuntimeError("daemon identity changed")

    def volume(self, suffix):
        name = self.tag+"-"+suffix
        self.docker("volume", "create", "--label", OWNER+"="+self.tag, name)
        self.volumes.append(name)
        return name

    def network(self):
        identity = self.docker("network", "create", "--internal", "--label", OWNER+"="+self.tag, self.tag).stdout.strip()
        self.networks.append(identity)
        return identity

    def create(self, code, arguments=(), *, network="none", mounts=(), alias=None):
        name = self.tag+"-"+str(len(self.containers))
        options = ["--name", name, "--label", OWNER+"="+self.tag, "--network", network,
                   "--memory", "64m", "--memory-swap", "64m", "--cpus", "1",
                   "--pids-limit", "64", "--cap-drop", "ALL", "--security-opt", "no-new-privileges"]
        if alias:
            options += ["--network-alias", alias]
        for mount in mounts:
            options += ["--mount", mount]
        identity = self.docker("create", *options, IMAGE, "python", "-c", code, *arguments).stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{64}", identity):
            raise RuntimeError("full fixture container ID required")
        self.containers.append(identity)
        self.owned_container(identity)
        return identity

    def owned_container(self, identity):
        value = self.inspect("container", identity)
        if value.get("Id") != identity or value.get("Config", {}).get("Labels", {}).get(OWNER) != self.tag:
            raise RuntimeError("fixture container ownership changed")
        return value

    def execute(self, code, arguments=(), *, expected=0, **kwargs):
        identity = self.create(code, arguments, **kwargs)
        self.docker("start", identity)
        result = self.docker("wait", identity, timeout=90)
        if int(result.stdout.strip()) != expected:
            raise RuntimeError("unexpected fixture container exit")
        return identity, self.docker("logs", "--tail", "30", identity).stdout.strip()

    def cleanup(self):
        self.check_daemon()
        for identity in reversed(self.containers):
            self.owned_container(identity)
            self.docker("rm", "--force", identity)
        for identity in reversed(self.networks):
            value = self.inspect("network", identity)
            if value.get("Id") != identity or value.get("Labels", {}).get(OWNER) != self.tag:
                raise RuntimeError("fixture network ownership changed")
            self.docker("network", "rm", identity)
        for name in reversed(self.volumes):
            value = self.inspect("volume", name)
            if value.get("Name") != name or value.get("Labels", {}).get(OWNER) != self.tag:
                raise RuntimeError("fixture volume ownership changed")
            self.docker("volume", "rm", name)
        if self.image_tag:
            if self.inspect("image", self.image_tag)["Id"] != self.image_id:
                raise RuntimeError("fixture image tag identity changed")
            self.docker("image", "rm", self.image_tag)
        self.cleanup_files()

    def cleanup_files(self):
        resolved = self.folder.resolve(strict=True)
        parent = Path(os.environ["RUNNER_TEMP"]).resolve(strict=True)
        if resolved != self.folder or resolved.parent != parent or not resolved.name.startswith("devops-container-"):
            raise RuntimeError("cleanup escaped owned fixture directory")
        if any(path.is_symlink() for path in resolved.rglob("*")):
            raise RuntimeError("refuse fixture cleanup through symlink")
        shutil.rmtree(resolved)
