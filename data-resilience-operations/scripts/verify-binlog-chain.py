#!/usr/bin/env python3
"""Verify declared recovery artifact bytes and file sequence, never replay SQL."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from pathlib import Path, PurePosixPath

MAX_BUDGET = 1 << 40
NAME = re.compile(r"([A-Za-z0-9_-]{1,64})\.(\d{6,10})\Z")
COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}\Z")
REFERENCE = re.compile(r"[a-z][a-z0-9_-]{0,30}:[A-Za-z0-9][A-Za-z0-9._-]{0,95}\Z")
RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError("fields")


def integer(value, minimum=0, maximum=MAX_BUDGET):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("integer")
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate key")
        result[key] = value
    return result


def no_link(path):
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError("link/reparse")
    return info


def artifact(root, record):
    relative = record["file"]
    if not isinstance(relative, str) or not relative or len(relative) > 512:
        raise ValueError("path")
    parts = relative.split("/")
    if len(parts) > 8 or any(not COMPONENT.fullmatch(part) or part.endswith(".") or part.split(".")[0].upper() in RESERVED for part in parts):
        raise ValueError("portable path")
    path = root
    for index, part in enumerate(parts):
        path = path / part
        info = no_link(path)
        if index < len(parts) - 1 and not stat.S_ISDIR(info.st_mode):
            raise ValueError("parent directory")
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError("regular unaliased artifact required")
    if info.st_size != record["size"]:
        raise ValueError("size")
    return path, info


def record_fields(value, log=False):
    fields(value, {"file", "size", "sha256", *({"name"} if log else set())})
    integer(value["size"], 4 if log else 1)
    if not isinstance(value["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", value["sha256"]):
        raise ValueError("digest")


def coordinate(value):
    fields(value, {"name", "position"})
    match = NAME.fullmatch(value["name"]) if isinstance(value["name"], str) else None
    if not match:
        raise ValueError("log name")
    integer(value["position"], 4)
    return match.group(1), match.group(2), int(match.group(2))


def verify(data, root, max_bytes=1 << 30):
    fields(data, {"schema_version", "engine", "source_ref", "coordinate_evidence_ref", "boundary_evidence_ref", "backup", "start", "stop", "logs"})
    if data["schema_version"] != "1.0" or data["engine"] not in ("mysql", "mariadb"):
        raise ValueError("schema/engine")
    for key in ("source_ref", "coordinate_evidence_ref", "boundary_evidence_ref"):
        if not isinstance(data[key], str) or not REFERENCE.fullmatch(data[key]):
            raise ValueError("evidence reference")
    integer(max_bytes, 1)
    start, stop = coordinate(data["start"]), coordinate(data["stop"])
    if start[0] != stop[0] or len(start[1]) != len(stop[1]) or stop[2] < start[2]:
        raise ValueError("history sequence")
    logs = data["logs"]
    if not isinstance(logs, list) or not 1 <= len(logs) <= 10000 or len(logs) != stop[2] - start[2] + 1:
        raise ValueError("log coverage")
    record_fields(data["backup"])
    for index, log in enumerate(logs):
        record_fields(log, log=True)
        expected = f"{start[0]}.{start[2] + index:0{len(start[1])}d}"
        if log["name"] != expected or not isinstance(log["file"], str) or PurePosixPath(log["file"]).name != expected:
            raise ValueError("log sequence/path")
    if data["start"]["position"] >= logs[0]["size"] or data["stop"]["position"] > logs[-1]["size"]:
        raise ValueError("position outside file")
    if len(logs) == 1 and data["stop"]["position"] <= data["start"]["position"]:
        raise ValueError("empty/reversed interval")
    records = [data["backup"], *logs]
    total = sum(item["size"] for item in records)
    if total > max_bytes:
        raise ValueError("I/O budget")
    root = Path(root).absolute()
    for parent in [*reversed(root.parents), root]:
        if not stat.S_ISDIR(no_link(parent).st_mode):
            raise ValueError("artifact root")
    paths, aliases, checked = [], set(), set()
    for record in records:
        path, info = artifact(root, record)
        alias = record["file"].casefold()
        identity = (info.st_dev, info.st_ino)
        if alias in aliases or identity in checked:
            raise ValueError("duplicate artifact")
        aliases.add(alias); checked.add(identity)
        paths.append((path, info, record))
    for index, (path, before, record) in enumerate(paths):
        descriptor = os.open(path, os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0))
        with os.fdopen(descriptor, "rb") as source:
            opened = os.fstat(source.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino) or opened.st_nlink != 1:
                raise ValueError("artifact changed")
            digest, remaining = hashlib.sha256(), record["size"]
            first = source.read(min(4, remaining)); remaining -= len(first); digest.update(first)
            if index and first != b"\xfebin":
                raise ValueError("plain binary log required")
            while remaining:
                block = source.read(min(1 << 20, remaining))
                if not block:
                    raise ValueError("truncated")
                digest.update(block); remaining -= len(block)
            after = os.fstat(source.fileno())
            if source.read(1) or digest.hexdigest() != record["sha256"]:
                raise ValueError("bytes differ")
            current = no_link(path)
            fingerprint = lambda x: (x.st_dev, x.st_ino, x.st_size, x.st_mtime_ns, x.st_nlink)
            # Windows stat/fstat ctime can use different creation/change semantics.
            # Compare ctime within the descriptor API; POSIX also compares the path.
            ctime_changed = opened.st_ctime_ns != after.st_ctime_ns
            if os.name != "nt": ctime_changed |= after.st_ctime_ns != current.st_ctime_ns
            if ctime_changed or fingerprint(opened) != fingerprint(after) or fingerprint(after) != fingerprint(current):
                raise ValueError("artifact changed")
    return {"status": "integrity_verified_replay_unproven", "engine": data["engine"],
            "artifact_count": len(records), "log_count": len(logs), "bytes_hashed": total,
            "required_next": "native decoding, transaction-boundary proof, isolated restore and core authorization"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--max-bytes", type=int, default=1 << 30)
    args = parser.parse_args()
    try:
        with args.receipt.open("rb") as source:
            payload = source.read(1_048_577)
        if len(payload) > 1_048_576:
            raise ValueError("receipt too large")
        data = json.loads(payload, object_pairs_hook=unique_object)
        result = verify(data, args.root, args.max_bytes)
    except (OSError, ValueError, TypeError, KeyError, RecursionError):
        print("ERROR: invalid recovery receipt, artifact integrity or I/O budget; replay is not authorized")
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
