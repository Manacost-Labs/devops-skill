"""Synthetic cross-job artifact fixture. Not a production admission verifier."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
from datetime import datetime
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener, urlopen
from zipfile import ZipFile

WORKFLOW = ".github/workflows/cicd-operations.yml"


def strict_json(value):
    if len(value) > 256 * 1024:
        raise ValueError("fixture JSON too large")
    def pairs(items):
        result = {}
        for key, item in items:
            if key in result:
                raise ValueError("duplicate fixture key")
            result[key] = item
        return result
    return json.loads(value, object_pairs_hook=pairs)


def context():
    names = ("repository", "repository_id", "run_id", "attempt", "source_sha", "event_sha", "head_repository_id", "event")
    result = {name: os.environ["FIXTURE_" + name.upper()] for name in names}
    for name in ("repository_id", "run_id", "attempt", "head_repository_id"):
        if not re.fullmatch(r"[1-9][0-9]*", result[name]):
            raise ValueError("invalid fixture numeric identity")
    for name in ("source_sha", "event_sha"):
        if not re.fullmatch(r"[a-f0-9]{40}", result[name]):
            raise ValueError("invalid fixture revision")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", result["repository"]):
        raise ValueError("invalid fixture repository")
    return result


def payload_bytes(ctx):
    return (json.dumps({"schema": 1, "context": ctx, "release": "synthetic-v2", "data_schema": 2}, sort_keys=True, separators=(",", ":")) + "\n").encode()


def validate_payload(value, expected_digest, ctx):
    if hashlib.sha256(value).hexdigest() != expected_digest:
        raise ValueError("payload digest mismatch")
    data = strict_json(value)
    if data != {"schema": 1, "context": ctx, "release": "synthetic-v2", "data_schema": 2}:
        raise ValueError("payload identity or shape mismatch")
    return data


def zip_payload(value):
    if len(value) > 1024 * 1024:
        raise ValueError("fixture archive too large")
    with ZipFile(io.BytesIO(value)) as archive:
        entries = archive.infolist()
        if len(entries) != 1:
            raise ValueError("unexpected archive members")
        entry = entries[0]
        path = PurePosixPath(entry.filename)
        mode = entry.external_attr >> 16
        if entry.filename != "payload.json" or path.is_absolute() or ".." in path.parts or stat.S_ISLNK(mode) or entry.file_size > 256 * 1024:
            raise ValueError("unsafe archive member")
        return archive.read(entry)


def check_metadata(artifact, run, ctx, artifact_id, archive_digest):
    expected_name = f"cicd-fixture-{ctx['run_id']}-{ctx['attempt']}"
    if artifact.get("id") != artifact_id or artifact.get("name") != expected_name or artifact.get("expired") is not False or artifact.get("digest") != "sha256:" + archive_digest:
        raise ValueError("artifact identity or archive digest mismatch")
    producer = artifact.get("workflow_run", {})
    for key, expected in (("id", int(ctx["run_id"])), ("repository_id", int(ctx["repository_id"])), ("head_repository_id", int(ctx["head_repository_id"])), ("head_sha", ctx["event_sha"])):
        if producer.get(key) != expected:
            raise ValueError("producer identity mismatch")
    if run.get("id") != int(ctx["run_id"]) or run.get("run_attempt") != int(ctx["attempt"]) or run.get("path") != WORKFLOW or run.get("event") != ctx["event"] or run.get("head_sha") != ctx["event_sha"]:
        raise ValueError("workflow attempt identity mismatch")
    if datetime.fromisoformat(artifact["created_at"].replace("Z", "+00:00")) < datetime.fromisoformat(run["run_started_at"].replace("Z", "+00:00")):
        raise ValueError("artifact predates this attempt")


def api_json(path):
    request = Request("https://api.github.com/" + path, headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"], "Accept": "application/vnd.github+json"})
    with urlopen(request, timeout=40) as response:
        return strict_json(response.read(256 * 1024 + 1))


def archive_bytes(path):
    class NoRedirect(HTTPRedirectHandler):
        def redirect_request(self, *_):
            return None
    request = Request("https://api.github.com/" + path, headers={"Authorization": "Bearer " + os.environ["GH_TOKEN"]})
    try:
        build_opener(NoRedirect).open(request, timeout=40)
    except HTTPError as error:
        if error.code != 302:
            raise
        location = error.headers["Location"]
    else:
        raise ValueError("expected artifact service redirect")
    parsed = urlsplit(location)
    if parsed.scheme != "https" or parsed.username or parsed.password or not parsed.hostname or not parsed.hostname.endswith((".blob.core.windows.net", ".githubusercontent.com")):
        raise ValueError("unexpected artifact storage endpoint")
    # Deliberately do not forward the GitHub bearer to the storage host.
    with urlopen(location, timeout=40) as response:
        value = response.read(1024 * 1024 + 1)
    if len(value) > 1024 * 1024:
        raise ValueError("fixture download too large")
    return value


def main():
    mode, directory = sys.argv[1:]
    folder = Path(directory)
    ctx = context()
    if mode == "build":
        folder.mkdir(parents=True, exist_ok=False)
        value = payload_bytes(ctx)
        (folder / "payload.json").write_bytes(value)
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
            stream.write("payload-digest=" + hashlib.sha256(value).hexdigest() + "\n")
        print("Created synthetic payload; no credentials or target data included")
    elif mode == "verify":
        artifact_id = int(os.environ["FIXTURE_ARTIFACT_ID"])
        archive_digest = os.environ["FIXTURE_ARCHIVE_DIGEST"].removeprefix("sha256:")
        expected_payload = os.environ["FIXTURE_PAYLOAD_DIGEST"]
        for digest in (archive_digest, expected_payload):
            if not re.fullmatch(r"[a-f0-9]{64}", digest):
                raise ValueError("missing fixture digest")
        prefix = "repos/" + ctx["repository"] + "/actions/"
        metadata = api_json(prefix + "artifacts/" + str(artifact_id))
        run = api_json(prefix + f"runs/{ctx['run_id']}/attempts/{ctx['attempt']}")
        check_metadata(metadata, run, ctx, artifact_id, archive_digest)
        transport = archive_bytes(prefix + f"artifacts/{artifact_id}/zip")
        if hashlib.sha256(transport).hexdigest() != archive_digest:
            raise ValueError("downloaded archive digest mismatch")
        original = zip_payload(transport)
        validate_payload(original, expected_payload, ctx)
        folder.mkdir(parents=True, exist_ok=False)
        (folder / "payload.json").write_bytes(original)
        print("Verified actual artifact ID/run/attempt/source and archive/payload bytes; unsigned fixture only")
    else:
        raise ValueError("unknown fixture command")


if __name__ == "__main__":
    main()
