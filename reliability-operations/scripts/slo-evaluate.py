#!/usr/bin/env python3
"""Calculate event-count SLO burn rates for explicit complete windows, offline."""
from __future__ import annotations

import argparse
import json
import re
from decimal import Decimal
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


def integer(value, minimum=0):
    if type(value) is not int or not minimum <= value <= 10**15:
        raise ValueError("counts/durations must be bounded integers")
    return value


def decimal(value):
    if type(value) not in {int, float, Decimal}:
        raise ValueError("numeric value required")
    result = Decimal(str(value))
    if not result.is_finite():
        raise ValueError("finite value required")
    return result


def evaluate(data):
    fields(data, {"objective", "windows", "alert"})
    objective = decimal(data["objective"])
    if not 0 < objective < 1:
        raise ValueError("objective must be between zero and one")
    windows = data["windows"]
    if not isinstance(windows, list) or not 2 <= len(windows) <= 100:
        raise ValueError("2-100 windows required")
    raw, results = {}, {}
    for window in windows:
        fields(window, {"name", "seconds", "total", "bad"})
        name = window["name"]
        if not isinstance(name, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{0,62}", name) or name in raw:
            raise ValueError("window names must be unique bounded identifiers")
        integer(window["seconds"], 1)
        total, bad = integer(window["total"]), integer(window["bad"])
        if bad > total:
            raise ValueError("bad cannot exceed total")
        ratio = Decimal(bad) / total if total else None
        burn = ratio / (1 - objective) if ratio is not None else None
        raw[name] = (window, burn)
        results[name] = {"error_ratio": str(ratio) if ratio is not None else None,
                         "burn_rate": str(burn) if burn is not None else None}
    alert = data["alert"]
    fields(alert, {"long", "short", "threshold", "minimum_events"})
    long_name, short_name = alert["long"], alert["short"]
    if not isinstance(long_name, str) or not isinstance(short_name, str) or long_name not in raw or short_name not in raw:
        raise ValueError("alert must reference existing windows")
    long, short = raw[long_name], raw[short_name]
    if long[0]["seconds"] <= short[0]["seconds"]:
        raise ValueError("long duration must exceed short")
    if (short[0]["bad"] > long[0]["bad"] or
            short[0]["total"] - short[0]["bad"] > long[0]["total"] - long[0]["bad"]):
        raise ValueError("short-window counts must be a subset of the long window")
    threshold = decimal(alert["threshold"])
    if not 0 < threshold <= 10**15:
        raise ValueError("threshold must be positive and bounded")
    minimum = integer(alert["minimum_events"], 1)
    if any(item[0]["total"] < minimum for item in (long, short)):
        status = "insufficient_data"
    else:
        status = "firing" if all(item[1] >= threshold for item in (long, short)) else "clear"
    return {"windows": results, "pair_status": status,
            "assumptions": "complete aligned windows with the same eligible-event definition"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="Secret-free JSON counts, objective and alert pair.")
    args = parser.parse_args()
    try:
        with args.input.open("rb") as source:
            payload = source.read(1_048_577)
        if len(payload) > 1_048_576:
            raise ValueError("input exceeds 1 MiB")
        result = evaluate(json.loads(payload, parse_float=Decimal, object_pairs_hook=unique_object))
    except (OSError, ValueError, TypeError, ArithmeticError, RecursionError):
        print("ERROR: invalid input; use the documented slo-evaluate schema")
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
