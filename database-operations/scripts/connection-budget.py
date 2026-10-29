#!/usr/bin/env python3
"""Calculate an explicit worst-case backend connection budget, offline."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


def fields(value, expected):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError("unexpected or missing fields")


def count(value, minimum=0):
    if type(value) is not int or not minimum <= value <= 1_000_000_000:
        raise ValueError("counts must be bounded integers")
    return value


def evaluate(data):
    fields(data, {"engine_max", "reserved", "other_peak", "pools"})
    maximum = count(data["engine_max"], 1)
    reserved = count(data["reserved"])
    other = count(data["other_peak"])
    if reserved >= maximum:
        raise ValueError("reserved must be smaller than engine_max")
    pools = data["pools"]
    if not isinstance(pools, list) or not 1 <= len(pools) <= 1000:
        raise ValueError("pools must contain 1-1000 entries")
    names, breakdown = set(), []
    for pool in pools:
        fields(pool, {"name", "instances", "per_instance"})
        name = pool["name"]
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,62}", name) or name in names:
            raise ValueError("pool names must be unique bounded identifiers")
        names.add(name)
        peak = count(pool["instances"], 1) * count(pool["per_instance"], 1)
        breakdown.append({"name": name, "backend_peak": peak})
    application = sum(item["backend_peak"] for item in breakdown)
    headroom = maximum - reserved - other - application
    return {
        "pools": breakdown, "application_peak": application,
        "usable_slots": maximum - reserved, "backend_peak": application + other,
        "committed_slots": application + other + reserved, "headroom": headroom,
        "status": "fits" if headroom > 0 else "at_limit" if headroom == 0 else "exceeds",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Explicit secret-free JSON counts; no target connection.")
    args = parser.parse_args()
    try:
        with args.input.open("rb") as source:
            payload = source.read(1_048_577)
        if len(payload) > 1_048_576:
            raise ValueError("input exceeds 1 MiB")
        data = json.loads(payload, object_pairs_hook=unique_object)
        result = evaluate(data)
    except (OSError, ValueError, TypeError, RecursionError):
        print("ERROR: invalid input; use the documented connection-budget schema")
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
