#!/usr/bin/env python3
"""Summarize one offline Docker inspect snapshot from bounded stdin; no daemon I/O."""
from __future__ import annotations

import argparse
import json
import re
import sys

MAX_BYTES = 1048576
MAX_ITEMS = 32


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def read_snapshot(stream):
    raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("snapshot too large")
    return json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_pairs,
                      parse_constant=lambda _: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def mapping(value):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("mapping required")
    return value


def number(value, minimum=0):
    if value is None:
        return None
    if type(value) is not int or not minimum <= value <= 2**63 - 1:
        raise ValueError("invalid number")
    return value


def boolean(value):
    if value is not None and type(value) is not bool:
        raise ValueError("invalid boolean")
    return value


def enum(value, allowed):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("invalid enum")
    return value if value in allowed else "other_or_unknown"


def summarize(data, expected_id):
    if not re.fullmatch(r"[0-9a-f]{64}", expected_id):
        raise ValueError("full container ID required")
    if not isinstance(data, list) or len(data) != 1 or not isinstance(data[0], dict):
        raise ValueError("exactly one container required")
    item = data[0]
    if item.get("Id") != expected_id:
        raise ValueError("identity mismatch")
    state = mapping(item.get("State"))
    host = mapping(item.get("HostConfig"))
    health = mapping(state.get("Health"))
    mounts = item.get("Mounts")
    if mounts is not None and (not isinstance(mounts, list) or any(not isinstance(m, dict) for m in mounts)):
        raise ValueError("invalid mounts")
    networks = mapping(item.get("NetworkSettings")).get("Networks")
    if networks is not None and not isinstance(networks, dict):
        raise ValueError("invalid networks")
    image = item.get("Image")
    if image is not None and (not isinstance(image, str) or not re.fullmatch(r"sha256:[0-9a-f]{64}", image)):
        raise ValueError("invalid image ID")
    error = state.get("Error")
    if error is not None and not isinstance(error, str):
        raise ValueError("invalid runtime error")
    unknown = [key for key, value in {
        "State": item.get("State"), "State.Status": state.get("Status"),
        "State.OOMKilled": state.get("OOMKilled"), "State.ExitCode": state.get("ExitCode"),
        "State.Running": state.get("Running"), "RestartCount": item.get("RestartCount"),
        "HostConfig": item.get("HostConfig"), "HostConfig.Memory": host.get("Memory"),
        "Mounts": mounts, "Networks": networks, "Image": image,
    }.items() if value is None]
    return {
        "status": "snapshot_observed", "verification": "not_assessed",
        "target_authenticity": "not_verified", "container_id": expected_id,
        "image_content_id": image, "registry_provenance": "not_verified",
        "state": enum(state.get("Status"), {"created", "running", "paused", "restarting", "removing", "exited", "dead"}),
        "running": boolean(state.get("Running")), "exit_code": number(state.get("ExitCode")),
        "oom_killed": boolean(state.get("OOMKilled")), "oom_cause": "not_determined",
        "restart_count": number(item.get("RestartCount")), "runtime_error_present": None if error is None else bool(error),
        "health": enum(health.get("Status"), {"starting", "healthy", "unhealthy"}),
        "health_absence": "not_configured_or_unreported" if not health else None,
        "limits": {"memory_bytes": number(host.get("Memory")), "memory_swap_setting_bytes": number(host.get("MemorySwap"), -1),
                   "nano_cpus": number(host.get("NanoCpus")), "pids_limit": number(host.get("PidsLimit"), -1)},
        "usage_and_host_pressure": "not_collected",
        "mount_count": None if mounts is None else len(mounts),
        "mounts": None if mounts is None else [{"index": index, "type": enum(m.get("Type"), {"volume", "bind", "tmpfs", "npipe"}),
                    "read_write": boolean(m.get("RW"))} for index, m in enumerate(mounts[:MAX_ITEMS])],
        "network_count": None if networks is None else len(networks),
        "mounts_truncated": mounts is not None and len(mounts) > MAX_ITEMS,
        "unknown_fields": unknown, "completeness": "partial" if unknown or (mounts is not None and len(mounts) > MAX_ITEMS) else "selected_fields_observed",
        "sensitive_text": "environment, commands, labels, health logs, paths and network details omitted",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--id", required=True, help="expected full 64-hex container ID from trusted target discovery")
    args = parser.parse_args()
    try:
        result = summarize(read_snapshot(sys.stdin.buffer), args.id)
    except (ValueError, TypeError, OSError, RecursionError):
        print(json.dumps({"status": "unknown", "verification": "not_assessed", "error": "invalid_or_mismatched_snapshot"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
