#!/usr/bin/env python3
"""Real actionlint and signed GitHub release verification; no deployment rights."""
from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
GH_SHA = "4c806978ffce1cec70853302a56d70ac6da4f19bae7adca4e1a8ab00633dd91d"
GH_SOURCE = "63837fb778d6a39f02be0ce76ff89f2bc8d74bdc"
ACTIONLINT_SHA = "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8"


def fetch(url, digest):
    with urlopen(url, timeout=90) as response:
        value = response.read(80 * 1024 * 1024 + 1)
    if len(value) > 80 * 1024 * 1024 or hashlib.sha256(value).hexdigest() != digest:
        raise RuntimeError("pinned tool archive failed verification")
    return value


def binary(archive, member, destination):
    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as source:
        entry = source.getmember(member)
        if not entry.isfile() or entry.size > 100 * 1024 * 1024:
            raise RuntimeError("unexpected pinned binary member")
        destination.write_bytes(source.extractfile(entry).read())
    destination.chmod(0o700)
    return str(destination)


def run(argv, expected=0, **kwargs):
    result = subprocess.run(argv, capture_output=True, text=True, timeout=120, **kwargs)
    if (result.returncode == 0) != (expected == 0):
        raise RuntimeError("fixture command outcome mismatch: " + result.stdout[-7000:] + result.stderr[-7000:])
    return result


def main():
    if not sys.platform.startswith("linux"):
        raise RuntimeError("native security fixture requires Linux; never skip")
    with tempfile.TemporaryDirectory(prefix="devops-cicd-tools-") as directory:
        folder = Path(directory)
        lint_archive = fetch("https://github.com/rhysd/actionlint/releases/download/v1.7.12/actionlint_1.7.12_linux_amd64.tar.gz", ACTIONLINT_SHA)
        lint = binary(lint_archive, "actionlint", folder / "actionlint")
        run([lint, "-shellcheck=", "-pyflakes=", *map(str, sorted((ROOT / ".github/workflows").glob("*.yml")))], cwd=ROOT)
        for name, body in {
            "missing-job": "on: push\njobs:\n  test:\n    needs: absent\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo test\n",
            "injection": "on: pull_request\njobs:\n  test:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo '${{ github.event.pull_request.title }}'\n",
        }.items():
            path = folder / (name + ".yml")
            path.write_text(body, encoding="utf-8")
            run([lint, "-shellcheck=", "-pyflakes=", str(path)], expected=1)
        marker = folder / "must-not-exist"
        title = "$(touch " + str(marker) + ")\n; exit 9"
        result = run(["bash", "-c", 'printf "%s" "$INPUT_TITLE"'], env=dict(os.environ, INPUT_TITLE=title))
        if result.stdout != title or marker.exists():
            raise RuntimeError("untrusted title escaped its data boundary")
        print("OK: real actionlint validates workflows and rejects dependency/injection fixtures", flush=True)

        gh_archive = fetch("https://github.com/cli/cli/releases/download/v2.103.3/gh_2.103.3_linux_amd64.tar.gz", GH_SHA)
        subject = folder / "gh-subject.tar.gz"
        subject.write_bytes(gh_archive)
        gh = binary(gh_archive, "gh_2.103.3_linux_amd64/bin/gh", folder / "gh")
        # The approved archive hash bootstraps the verifier. Verifying its own
        # release is a native provenance test, not an independent bootstrap.
        policy = ["--repo", "cli/cli", "--signer-workflow", "cli/cli/.github/workflows/deployment.yml", "--signer-digest", GH_SOURCE,
                  "--source-digest", GH_SOURCE, "--source-ref", "refs/heads/trunk", "--deny-self-hosted-runners", "--format", "json"]
        result = run([gh, "attestation", "verify", str(subject), *policy])
        verified = json.loads(result.stdout)
        if not verified:
            raise RuntimeError("no authenticated attestations")
        for item in verified:
            certificate = item["verificationResult"]["signature"]["certificate"]
            if certificate["sourceRepositoryIdentifier"] != "212613049" or certificate["sourceRepositoryDigest"] != GH_SOURCE or certificate["runnerEnvironment"] != "github-hosted":
                raise RuntimeError("authenticated certificate policy mismatch")
        bundle = folder / "verified-bundles.jsonl"
        bundle.write_text("\n".join(json.dumps(item["attestation"]["bundle"]) for item in verified) + "\n", encoding="utf-8")
        # Reuse authentic bundles so tampering fails subject verification rather
        # than merely querying a nonexistent digest at an online endpoint.
        tampered = folder / "tampered.tar.gz"
        tampered.write_bytes(gh_archive[:-1] + bytes([gh_archive[-1] ^ 1]))
        run([gh, "attestation", "verify", str(tampered), *policy, "--bundle", str(bundle)], expected=1)
        wrong_signer = list(policy)
        wrong_signer[wrong_signer.index("cli/cli/.github/workflows/deployment.yml")] = "cli/cli/.github/workflows/not-the-signer.yml"
        run([gh, "attestation", "verify", str(subject), *wrong_signer, "--bundle", str(bundle)], expected=1)
        wrong_source = list(policy)
        wrong_source[wrong_source.index("--source-digest") + 1] = "0" * 40
        run([gh, "attestation", "verify", str(subject), *wrong_source, "--bundle", str(bundle)], expected=1)
        print("OK: real signature/subject/certificate/source verification; tampered bytes, signer and source rejected", flush=True)


if __name__ == "__main__":
    main()
