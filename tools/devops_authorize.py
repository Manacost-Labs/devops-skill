#!/usr/bin/env python3
"""Offline owner signing; run outside the agent principal with a private key.

This program does not generate keys, derive human identity from a prompt, install
trust roots, edit a broker registry, or approve a candidate by itself.
"""
import argparse
import base64
import importlib.util
from pathlib import Path
import sys

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("owner_broker_contract", ROOT / "devops-platform-contracts/scripts/broker_contract.py")
C = importlib.util.module_from_spec(spec)
spec.loader.exec_module(C)


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--private-key", type=Path, required=True)
    parser.add_argument("--key-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        C.identifier(args.key_id)
        candidate = C.read_record(args.candidate)
        fields = C.GRANT_FIELDS if candidate.get("kind") == "grant" else C.ADMISSION_FIELDS
        C.exact(candidate, fields | {"signatures"})
        if not isinstance(candidate["signatures"], list) or any(item.get("key_id") == args.key_id for item in candidate["signatures"]):
            raise C.Denied("duplicate or malformed signatures")
        # Owner key must be separately protected; never include it in output.
        metadata = args.private_key.lstat()
        if metadata.st_size > 16384 or args.private_key.is_symlink():
            raise C.Denied("invalid owner key file")
        key = serialization.load_pem_private_key(args.private_key.read_bytes(), password=None)
        if not isinstance(key, Ed25519PrivateKey):
            raise C.Denied("Ed25519 owner key required")
        payload = {name: value for name, value in candidate.items() if name != "signatures"}
        signature = key.sign(C.DOMAIN + C.canonical(payload))
        candidate["signatures"].append({"key_id": args.key_id, "signature": base64.b64encode(signature).decode("ascii")})
        # Exclusive output prevents silently overwriting a reviewed authorization.
        with args.output.open("xb") as output:
            output.write(C.canonical(candidate) + b"\n")
        print("SIGNED: candidate only; broker independently checks trust, scope, expiry and policy")
        return 0
    except Exception:
        print("BLOCKED: invalid candidate, unavailable owner key or occupied output")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
