#!/usr/bin/env python3
"""Offline comparison of bounded native Linux/FRR snapshots. Never executes input."""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import sys
from pathlib import Path

MAX_BYTES = 8 * 1024 * 1024


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def load(path):
    with Path(path).open("rb") as stream:
        data = stream.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise ValueError("snapshot too large")
    return json.loads(data, object_pairs_hook=unique_pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def prefix(value):
    if not isinstance(value, str):
        raise ValueError("invalid prefix")
    return str(ipaddress.ip_network(value, strict=True))


def records(value, required):
    if not isinstance(value, list) or any(not isinstance(row, dict) or not required <= row.keys() for row in value):
        raise ValueError("unsupported native records")
    return value


def normalize_nft(value):
    """Preserve expression/rule order and every semantic field; ignore only runtime IDs/counts."""
    if not isinstance(value, dict) or set(value) != {"nftables"} or not isinstance(value["nftables"], list):
        raise ValueError("invalid nft snapshot")
    output = []
    for entry in value["nftables"]:
        if not isinstance(entry, dict) or len(entry) != 1:
            raise ValueError("invalid nft object")
        kind, body = next(iter(entry.items()))
        if kind == "metainfo":
            continue
        if kind not in {"table", "chain", "rule"} or not isinstance(body, dict):
            raise ValueError("unsupported nft object; manual review required")
        if not {"family", "table" if kind != "table" else "name"} <= body.keys():
            raise ValueError("missing nft identity")
        body = {key: item for key, item in body.items() if key not in {"handle", "index"}}
        if kind == "rule":
            if not isinstance(body.get("chain"), str) or not isinstance(body.get("expr"), list):
                raise ValueError("invalid nft rule")
            expressions = []
            for expression in body["expr"]:
                if not isinstance(expression, dict) or len(expression) != 1:
                    raise ValueError("invalid nft expression")
                if "counter" in expression:
                    counter = expression["counter"]
                    if not isinstance(counter, dict) or set(counter) != {"packets", "bytes"}:
                        raise ValueError("unsupported named counter")
                    expression = {"counter": {"packets": 0, "bytes": 0}}
                expressions.append(expression)
            body["expr"] = expressions
        output.append({kind: body})
    return output


def normalize(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != {"routes", "rules", "nft", "bgp"}:
        raise ValueError("snapshot requires routes, rules, nft, bgp")
    routes = records(snapshot["routes"], {"dst"})
    for route in routes:
        if route["dst"] != "default":
            prefix(route["dst"])
    rules = records(snapshot["rules"], {"priority"})
    priorities = [row["priority"] for row in rules]
    if any(type(item) is not int or item < 0 for item in priorities) or len(set(priorities)) != len(priorities):
        raise ValueError("ambiguous routing policy priority")
    bgp = snapshot["bgp"]
    if not isinstance(bgp, dict) or not isinstance(bgp.get("routes"), dict):
        raise ValueError("FRR full IPv4 unicast JSON required")
    prefixes = []
    for destination, paths in bgp["routes"].items():
        if not isinstance(paths, list) or not paths or any(not isinstance(path, dict) for path in paths):
            raise ValueError("invalid FRR paths")
        prefixes.append(prefix(destination))
    return {"routes": sorted(routes, key=canonical),
            "rules": sorted(rules, key=lambda row: row["priority"]),
            "nft": normalize_nft(snapshot["nft"]),
            "bgp_prefixes": sorted(prefixes)}


def difference(before, after):
    old, new = set(map(canonical, before)), set(map(canonical, after))
    return {"removed": [json.loads(item) for item in sorted(old - new)],
            "added": [json.loads(item) for item in sorted(new - old)]}


def audit(before, intended, observed, allowed_prefixes):
    baseline, target, actual = map(normalize, (before, intended, observed))
    allowed = set(map(prefix, allowed_prefixes))
    # Exact membership: an allowed /24 never authorizes an unexpected /25 or /0.
    leaks = sorted(set(actual["bgp_prefixes"]) - allowed)
    drift = [key for key in target if target[key] != actual[key]]
    return {"status": "BLOCKED" if leaks or drift else "MATCHED",
            "observed_digest": "sha256:" + hashlib.sha256(canonical(actual).encode()).hexdigest(),
            "drift_sections": drift, "unexpected_bgp_prefixes": leaks,
            "route_diff": difference(baseline["routes"], actual["routes"]),
            "policy_rule_diff": difference(baseline["rules"], actual["rules"]),
            "acl_order_or_content_changed": baseline["nft"] != actual["nft"],
            "bgp_prefix_diff": difference(baseline["bgp_prefixes"], actual["bgp_prefixes"]),
            "limits": "snapshot comparison only; no authorization, freshness, peer health, BGP path attributes or packet verdict proof"}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("before", "intended", "observed"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--allowed-prefix", action="append", default=[])
    args = parser.parse_args(argv)
    try:
        result = audit(load(args.before), load(args.intended), load(args.observed), args.allowed_prefix)
    except (OSError, ValueError, TypeError, RecursionError, OverflowError):
        print(json.dumps({"status": "BLOCKED", "error": "invalid or unsupported snapshot; inspect locally"}))
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0 if result["status"] == "MATCHED" else 1


if __name__ == "__main__":
    sys.exit(main())
