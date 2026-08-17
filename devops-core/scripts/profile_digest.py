#!/usr/bin/env python3
"""Validate and calculate a canonical SHA-256 fingerprint for a target profile."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import yaml


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: profile_digest.py <target-profile.yaml>")
        return 2
    path = Path(sys.argv[1])
    validator = Path(__file__).with_name("validate_contracts.py")
    result = subprocess.run([sys.executable, str(validator), str(path)], capture_output=True, text=True)
    if result.returncode:
        print(result.stdout + result.stderr, end="")
        return result.returncode
    try:
        profile = yaml.safe_load(path.read_text(encoding="utf-8-sig"))
        canonical = json.dumps(profile, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        print("sha256:" + hashlib.sha256(canonical).hexdigest())
        return 0
    except (OSError, yaml.YAMLError, TypeError, ValueError) as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
