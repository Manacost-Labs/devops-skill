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
    network = ipaddress.ip_network(value, strict=True)
    if network.version != 4:
        raise ValueError("IPv6 requires a separately supported collection")
    return str(network)


def records(value, required):
    if not isinstance(value, list) or any(not isinstance(row, dict) or not required <= row.keys() for row in value):
        raise ValueError("unsupported native records")
    return value


def native_fields(row, *, integer=(), text=(), scalar=()):
    """Validate known native field types without interpreting opaque extensions."""
    for field in integer:
        if field in row and (type(row[field]) is not int or row[field] < 0):
            raise ValueError("invalid native integer field")
    for field in text:
        if field in row and (not isinstance(row[field], str) or not row[field]):
            raise ValueError("invalid native text field")
    for field in scalar:
        if field in row and (type(row[field]) not in {str, int} or row[field] == "" or (type(row[field]) is int and row[field] < 0)):
            raise ValueError("invalid native scalar field")


def routing_fields(row):
    native_fields(row, integer=("metric", "nhid", "mtu", "advmss"),
                  text=("dev", "gateway", "prefsrc", "src", "type", "pref", "from"),
                  scalar=("table", "protocol", "scope"))
    for field in ("gateway", "prefsrc"):
        if field in row and ipaddress.ip_address(row[field]).version != 4:
            raise ValueError("IPv6 next hop/source outside supported collection")
    if "flags" in row and (not isinstance(row["flags"], list) or any(not isinstance(item, str) for item in row["flags"])):
        raise ValueError("invalid route flags")
    if "nexthops" in row:
        if not isinstance(row["nexthops"], list) or not row["nexthops"]:
            raise ValueError("invalid multipath route")
        for hop in row["nexthops"]:
            if not isinstance(hop, dict) or not hop:
                raise ValueError("invalid multipath hop")
            native_fields(hop, integer=("weight",), text=("dev", "gateway"))
            if "gateway" in hop and ipaddress.ip_address(hop["gateway"]).version != 4:
                raise ValueError("IPv6 multipath outside supported collection")


def normalize_nft(value):
    """Preserve expression/rule order and every semantic field; ignore only runtime IDs/counts."""
    if not isinstance(value, dict) or set(value) != {"nftables"} or not isinstance(value["nftables"], list):
        raise ValueError("invalid nft snapshot")
    output = []
    tables, chains = set(), set()
    for entry in value["nftables"]:
        if not isinstance(entry, dict) or len(entry) != 1:
            raise ValueError("invalid nft object")
        kind, body = next(iter(entry.items()))
        if kind == "metainfo":
            if not isinstance(body, dict): raise ValueError("invalid nft metainfo")
            continue
        if kind not in {"table", "chain", "rule"} or not isinstance(body, dict):
            raise ValueError("unsupported nft object; manual review required")
        identity = ("family", "name") if kind == "table" else ("family", "table", "chain" if kind == "rule" else "name")
        if any(not isinstance(body.get(field), str) or not body[field] for field in identity):
            raise ValueError("missing nft identity")
        native_fields(body, integer=("handle", "index"), text=("comment", "hook", "type", "policy", "dev"))
        if "prio" in body and (type(body["prio"]) not in {str, int} or body["prio"] == ""):
            raise ValueError("invalid nft chain priority")
        if kind == "table":
            key = (body["family"], body["name"])
            if key in tables: raise ValueError("duplicate nft table")
            tables.add(key)
        else:
            if (body["family"], body["table"]) not in tables:
                raise ValueError("nft object has no preceding table")
            key = (body["family"], body["table"], body["chain" if kind == "rule" else "name"])
            if kind == "chain":
                if key in chains: raise ValueError("duplicate nft chain")
                chains.add(key)
            elif key not in chains:
                raise ValueError("nft rule has no preceding chain")
        body = {key: item for key, item in body.items() if key not in {"handle", "index"}}
        if kind == "rule":
            if not isinstance(body.get("chain"), str) or not isinstance(body.get("expr"), list) or not body["expr"]:
                raise ValueError("invalid nft rule")
            expressions = []
            for expression in body["expr"]:
                if not isinstance(expression, dict) or len(expression) != 1:
                    raise ValueError("invalid nft expression")
                if any(verdict in expression and expression[verdict] is not None for verdict in ("accept", "drop", "return", "continue", "notrack")):
                    raise ValueError("invalid nft verdict shape")
                if "counter" in expression:
                    counter = expression["counter"]
                    if not isinstance(counter, dict) or set(counter) != {"packets", "bytes"}:
                        raise ValueError("unsupported named counter")
                    if any(type(item) is not int or item < 0 for item in counter.values()):
                        raise ValueError("invalid counter value")
                    expression = {"counter": {"packets": 0, "bytes": 0}}
                expressions.append(expression)
            body["expr"] = expressions
        output.append({kind: body})
    return output


def normalize(snapshot):
    if not isinstance(snapshot, dict) or set(snapshot) != {"routes", "rules", "nft", "bgp"}:
        raise ValueError("snapshot requires routes, rules, nft, bgp")
    routes = records(snapshot["routes"], {"dst"})
    if len(set(map(canonical, routes))) != len(routes):
        raise ValueError("duplicate route records")
    for route in routes:
        routing_fields(route)
        if route["dst"] != "default":
            prefix(route["dst"])
    rules = records(snapshot["rules"], {"priority"})
    priorities = [row["priority"] for row in rules]
    if any(type(item) is not int or item < 0 for item in priorities) or len(set(priorities)) != len(priorities):
        raise ValueError("ambiguous routing policy priority")
    for rule in rules:
        native_fields(rule, text=("src", "dst", "iif", "oif", "action", "ipproto"),
                      scalar=("table", "fwmark", "fwmask"))
        for field in ("src", "dst"):
            if field in rule and rule[field] != "all": prefix(rule[field])
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
