#!/usr/bin/env python3
"""Capture one bounded Cloudflare API observation; no writes, retries or redirects."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import re
import urllib.error
import urllib.request

SPEC = importlib.util.spec_from_file_location("cloudflare_state_guard", Path(__file__).with_name("state-guard.py"))
GUARD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GUARD)
API = "https://api.cloudflare.com/client/v4"
KINDS = {"access-app", "access-policy", "waf-ruleset", "tunnel-config", "worker-deployments"}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("redirect refused")


def endpoint(kind, account, zone, resource):
    if kind not in KINDS or any(not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value) for value in (account, zone)):
        raise ValueError("target identity")
    if not isinstance(resource, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", resource):
        raise ValueError("resource identity")
    if kind == "waf-ruleset":
        return f"/zones/{zone}/rulesets/{resource}"
    paths = {"access-app": "access/apps", "access-policy": "access/policies", "tunnel-config": "cfd_tunnel", "worker-deployments": "workers/scripts"}
    suffix = {"tunnel-config": "/configurations", "worker-deployments": "/deployments"}.get(kind, "")
    return f"/accounts/{account}/{paths[kind]}/{resource}{suffix}"


def read_once(opener, path, token):
    request = urllib.request.Request(API + path, headers={"Authorization": "Bearer " + token, "Accept": "application/json"}, method="GET")
    with opener.open(request, timeout=15) as response:
        if response.status != 200:
            raise ValueError("unexpected HTTP status")
        raw = response.read(GUARD.LIMIT + 1)
    if len(raw) > GUARD.LIMIT:
        raise ValueError("response too large")
    data = json.loads(raw.decode("utf-8"), object_pairs_hook=GUARD.unique, parse_constant=GUARD.reject_constant)
    if not isinstance(data, dict) or data.get("success") is not True or data.get("errors") or "result" not in data:
        raise ValueError("provider error/shape")
    GUARD.inspect_tree(data["result"])
    GUARD.digest(data["result"])
    pagination = data.get("result_info")
    if pagination is not None and not isinstance(pagination, dict):
        raise ValueError("pagination shape")
    GUARD.inspect_tree(pagination)
    GUARD.digest(pagination)
    return data["result"], "sha256:" + hashlib.sha256(raw).hexdigest(), pagination


def validate_result(kind, resource, result):
    if not isinstance(result, dict):
        raise ValueError("result shape")
    if kind in {"access-app", "access-policy", "waf-ruleset"} and result.get("id") != resource:
        raise ValueError("returned object identity")
    if kind == "access-app" and not isinstance(result.get("type"), str):
        raise ValueError("application shape")
    if kind == "access-policy" and (not isinstance(result.get("decision"), str) or result["decision"] not in {"allow", "deny", "bypass", "non_identity"} or not isinstance(result.get("include"), list)):
        raise ValueError("policy shape")
    if kind == "waf-ruleset" and (not isinstance(result.get("phase"), str) or not isinstance(result.get("version"), str) or not isinstance(result.get("rules"), list)):
        raise ValueError("ruleset shape")
    if kind == "tunnel-config" and (result.get("tunnel_id") != resource or type(result.get("version")) is not int or result["version"] < 0 or not isinstance(result.get("config"), dict)):
        raise ValueError("tunnel configuration shape")
    if kind == "worker-deployments":
        deployments = result.get("deployments")
        if not isinstance(deployments, list):
            raise ValueError("deployments shape")
        for deployment in deployments:
            if not isinstance(deployment, dict) or not isinstance(deployment.get("id"), str) or not isinstance(deployment.get("versions"), list) or not deployment["versions"]:
                raise ValueError("deployment shape")
            total = 0
            for version in deployment["versions"]:
                if not isinstance(version, dict) or not isinstance(version.get("version_id"), str) or type(version.get("percentage")) not in {int, float} or not 0 < version["percentage"] <= 100:
                    raise ValueError("deployment split shape")
                total += version["percentage"]
            if abs(total - 100) > 0.000001:
                raise ValueError("deployment split total")


def capture(kind, account, zone, resource, token, opener=None):
    path = endpoint(kind, account, zone, resource)
    if not isinstance(token, str) or not token or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise ValueError("credential profile unavailable")
    if opener is None:
        # Avoid sending credentials through an ambient proxy; HTTPS keeps default TLS validation.
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    zone_result, _, _ = read_once(opener, f"/zones/{zone}", token)
    if not isinstance(zone_result, dict) or zone_result.get("id") != zone or not isinstance(zone_result.get("account"), dict) or zone_result["account"].get("id") != account:
        raise ValueError("account/zone mismatch")
    result, response_digest, pagination = read_once(opener, path, token)
    validate_result(kind, resource, result)
    return {"schema_version": 1, "kind": kind, "account_id": account, "zone_id": zone, "resource_id": resource, "collected_at": datetime.now(timezone.utc).isoformat(), "response_digest": response_digest, "coverage": "one_api_response_only", "provider_behavior_verified": False, "pagination": pagination, "result": result}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kind", choices=sorted(KINDS), required=True)
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--zone-id", required=True)
    parser.add_argument("--resource-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.output.exists():
            raise ValueError("output exists")
        result = capture(args.kind, args.account_id, args.zone_id, args.resource_id, os.environ.get("CLOUDFLARE_API_TOKEN", ""))
        # O_EXCL prevents accidental evidence replacement; private local ACLs remain operator-owned.
        fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            json.dump(result, output, indent=2, allow_nan=False)
            output.write("\n")
        print('{"status":"captured","coverage":"one_api_response_only","provider_behavior_verified":false}')
        return 0
    except (ValueError, TypeError, OSError, RecursionError, OverflowError, urllib.error.URLError, http.client.HTTPException):
        print('{"status":"blocked","detail":"observation unavailable; raw provider errors suppressed"}')
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
