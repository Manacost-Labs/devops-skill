#!/usr/bin/env python3
"""Resolve installed modules whose declared capabilities cover a requested set."""
from __future__ import annotations

import argparse
import json
from itertools import combinations
from pathlib import Path

import yaml

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ROOT = PACKAGE_ROOT.parent
CATALOG_PATH = ROOT / "catalog.json" if (ROOT / "catalog.json").is_file() else PACKAGE_ROOT / "catalog.json"


def minimum_cover(candidates: list[dict], target: set[str]) -> list[dict]:
    """Return the smallest deterministic module set that covers target."""
    if not target:
        return []
    ordered = sorted(candidates, key=lambda candidate: candidate["module"])
    for size in range(1, len(ordered) + 1):
        for group in combinations(ordered, size):
            group_coverage = set().union(*(candidate["covered"] for candidate in group))
            if target <= group_coverage:
                return list(group)
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--capability", action="append", required=True)
    args = parser.parse_args()
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig"))
    requested = set(args.capability)
    candidates = []
    for name, meta in catalog["skills"].items():
        manifest_path = ROOT / name / "module.yaml"
        if not manifest_path.is_file():
            continue
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8-sig"))
        available = set(manifest.get("capabilities", []))
        module_coverage = requested & available
        if module_coverage:
            candidates.append({
                "module": name,
                "role": meta["role"],
                "covered": module_coverage,
                "missing": sorted(requested - available),
            })

    candidates.sort(key=lambda candidate: candidate["module"])
    covered = set().union(*(candidate["covered"] for candidate in candidates)) if candidates else set()
    unresolved = requested - covered
    selected_candidates = minimum_cover(candidates, covered)
    remaining = set(covered)
    handoffs = []
    for candidate in selected_candidates:
        assigned = sorted(remaining & candidate["covered"])
        handoffs.append({
            "module": candidate["module"],
            "role": candidate["role"],
            "capabilities": assigned,
        })
        remaining -= set(assigned)

    for candidate in candidates:
        candidate["covered"] = sorted(candidate["covered"])

    result = {
        "requested": sorted(requested),
        "covered": sorted(covered),
        "unresolved": sorted(unresolved),
        "selected": [candidate["module"] for candidate in selected_candidates],
        "selection_policy": "minimum-module-count-then-module-name",
        "candidates": candidates,
        "handoffs": handoffs,
    }
    print(json.dumps(result, indent=2))
    return 1 if unresolved else 0


if __name__ == "__main__":
    raise SystemExit(main())
