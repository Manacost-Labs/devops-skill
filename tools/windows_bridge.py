#!/usr/bin/env python3
"""Protected worker-only PSRP bridge. Never a general PowerShell client."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import re
import stat
import sys

LIMIT = 65536
DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
CONTEXT = {"operation_id", "task_id", "target_id", "call_digest", "grant_digest", "registry_digest", "epoch", "not_before", "expires", "parameters_digest", "target_digest"}


class Refused(ValueError):
    pass


def require(condition):
    if not condition:
        raise Refused("invalid protected Windows task binding")


def exact(value, fields):
    require(isinstance(value, dict) and set(value) == set(fields))


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False).encode("ascii")


def digest(value):
    return "sha256:" + hashlib.sha256(canonical(value)).hexdigest()


def decode(raw):
    require(isinstance(raw, (str, bytes)) and len(raw) <= LIMIT)
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result)
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: require(False))


def window(context):
    start, end = (datetime.fromisoformat(context[key].replace("Z", "+00:00")) for key in ("not_before", "expires"))
    require(start.tzinfo is not None and end.tzinfo is not None)
    require(start <= datetime.now(timezone.utc) < end and 0 < (end-start).total_seconds() <= 7200)


def validate(value, path_type=Path):
    exact(value, {"schema_version", "context", "parameters", "target"})
    require(value["schema_version"] == "2.0")
    context, target = value["context"], value["target"]
    exact(context, CONTEXT)
    require(isinstance(context["operation_id"], str) and re.fullmatch(r"ops-[a-z0-9-]{6,76}", context["operation_id"]))
    for field in ("task_id", "target_id"):
        require(isinstance(context[field], str) and re.fullmatch(r"[a-z][a-z0-9-]{5,79}", context[field]))
    for field in ("call_digest", "grant_digest", "registry_digest", "parameters_digest", "target_digest"):
        require(isinstance(context[field], str) and DIGEST.fullmatch(context[field]))
    require(isinstance(context["epoch"], str) and re.fullmatch(r"[0-9a-f]{64}", context["epoch"]))
    require(isinstance(value["parameters"], dict) and len(value["parameters"]) <= 32)
    for key, item in value["parameters"].items():
        require(re.fullmatch(r"[a-z][a-z0-9_]{0,31}", key) and type(item) in (str, int, bool))
        require(not isinstance(item, str) or len(item) <= 256)
        require(type(item) is not int or -(2**53) < item < 2**53)
    require(context["parameters_digest"] == digest(value["parameters"]) and context["target_digest"] == digest(target))
    exact(target, {"kind", "server", "port", "configuration_name", "ca_file", "authentication", "binding_digest"})
    require(target["kind"] == "windows-jea-v1" and type(target["port"]) is int and 1 <= target["port"] <= 65535)
    require(isinstance(target["server"], str) and re.fullmatch(r"(?=.{1,253}$)[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*", target["server"]))
    require(isinstance(target["configuration_name"], str) and re.fullmatch(r"DevopsBound-[a-z0-9-]{6,64}", target["configuration_name"]))
    require(isinstance(target["binding_digest"], str) and DIGEST.fullmatch(target["binding_digest"]))
    require(isinstance(target["ca_file"], str) and path_type(target["ca_file"]).is_absolute())
    authentication = target["authentication"]
    require(isinstance(authentication, dict))
    if authentication.get("method") == "kerberos":
        exact(authentication, {"method", "cache_file"})
        require("." in target["server"] and re.search(r"[a-z]", target["server"]))
    else:
        exact(authentication, {"method", "certificate_pem", "certificate_key_pem"})
        require(authentication["method"] == "certificate")
    for field, path in authentication.items():
        require(field == "method" or isinstance(path, str) and path_type(path).is_absolute())
    window(context)
    return context, target


class PSRP:
    """Exactly three commands over one validated, nondelegating endpoint."""
    def __init__(self, target):
        from pypsrp.powershell import PowerShell, RunspacePool
        from pypsrp.wsman import WSMan
        authentication = target["authentication"]
        # Windows SSPI can use the interactive identity instead of a FILE
        # cache. Never replace the registered Linux connector identity silently.
        require(authentication["method"] != "kerberos" or os.name == "posix")
        secret = Path(authentication["cache_file"] if authentication["method"] == "kerberos" else authentication["certificate_key_pem"])
        metadata = secret.lstat()
        require(stat.S_ISREG(metadata.st_mode) and not secret.is_symlink() and metadata.st_nlink == 1)
        if os.name == "posix":
            require(metadata.st_uid == os.geteuid() and metadata.st_mode & 0o077 == 0)
        # No password/keytab acquisition, proxy, .netrc, credential delegation or
        # authentication downgrade. The owner supplies a finite worker cache.
        for key in list(os.environ):
            if key.casefold().endswith("_proxy") or key in {"NETRC", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE", "KRB5_CLIENT_KTNAME", "KRB5_KTNAME"}:
                os.environ.pop(key, None)
        os.environ.pop("KRB5CCNAME", None)
        if authentication["method"] == "kerberos":
            os.environ["KRB5CCNAME"] = "FILE:" + str(secret)
        logging.disable(logging.CRITICAL)  # Libraries may log SOAP/error bodies.
        arguments = {key: value for key, value in authentication.items() if key not in {"method", "cache_file"}}
        self.connection = WSMan(target["server"], port=target["port"], ssl=True, auth=authentication["method"], cert_validation=target["ca_file"],
            no_proxy=True, reconnection_retries=0, connection_timeout=10, operation_timeout=15, read_timeout=20,
            negotiate_delegate=False, negotiate_send_cbt=True, **arguments)
        transport = self.connection.transport
        session = transport._build_session()
        session.trust_env = False
        session.proxies = {}
        original = session.send
        expected = transport.endpoint
        def send(request, **kwargs):
            require(request.url == expected)
            kwargs["allow_redirects"] = False
            response = original(request, **kwargs)
            require(not 300 <= response.status_code < 400)
            return response
        session.send = send
        transport.session = session
        self.pool = RunspacePool(self.connection, configuration_name=target["configuration_name"], min_runspaces=1, max_runspaces=1)
        self.PowerShell = PowerShell

    def __enter__(self):
        self.pool.open()
        return self

    def __exit__(self, *_):
        self.pool.close()
        self.connection.close()

    def invoke(self, command, parameters):
        require(command in {"Get-DevopsEndpointBinding", "Get-DevopsBoundTaskStatus", "Invoke-DevopsBoundTask"})
        pipeline = self.PowerShell(self.pool)
        pipeline.add_cmdlet(command)
        for name, item in parameters.items():
            pipeline.add_parameter(name, item)
        output = pipeline.invoke()
        require(not pipeline.had_errors and len(output) == 1 and isinstance(output[0], str))
        return decode(output[0])


def run(value, route="execute", transport=PSRP):
    context, target = validate(value)
    attempted = False
    try:
        with transport(target) as client:
            binding = client.invoke("Get-DevopsEndpointBinding", {})
            exact(binding, {"binding_digest", "target_id"})
            require(binding == {"binding_digest": target["binding_digest"], "target_id": context["target_id"]})
            if route == "status":
                exact(value["parameters"], {"original_call_digest"})
                require(DIGEST.fullmatch(value["parameters"]["original_call_digest"]))
                receipt = client.invoke("Get-DevopsBoundTaskStatus", {"CallDigest": value["parameters"]["original_call_digest"]})
                exact(receipt, {"status", "call_digest", "binding_digest"})
                require(receipt["call_digest"] == value["parameters"]["original_call_digest"] and receipt["binding_digest"] == target["binding_digest"])
                require(receipt["status"] in {"not_observed", "executed", "outcome_unknown"})
                return {"state": receipt["status"]}, 0
            window(context)
            attempted = True  # Network failure from this point is uncertain.
            receipt = client.invoke("Invoke-DevopsBoundTask", {"BindingDigest": target["binding_digest"],
                "ContextJson": canonical(context).decode("ascii"), "ParametersJson": canonical(value["parameters"]).decode("ascii")})
            exact(receipt, {"operation_id", "call_digest", "binding_digest", "status", "result"})
            require(receipt["operation_id"] == context["operation_id"] and receipt["call_digest"] == context["call_digest"])
            require(receipt["binding_digest"] == target["binding_digest"] and receipt["status"] == "executed" and isinstance(receipt["result"], dict))
            return receipt["result"], 0
    except Exception:
        # No retry, fallback endpoint or raw error output. Even client close can
        # fail after a mutation: preserve broker/Windows receipts for the owner.
        return None, 4 if attempted else 3


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--route", choices=("execute", "status"), default="execute")
    args = parser.parse_args()
    try:
        value = decode(sys.stdin.buffer.read(LIMIT + 1))
        result, code = run(value, args.route)
        if code == 0:
            sys.stdout.buffer.write(canonical(result) + b"\n")
        else:
            print("WINDOWS_OUTCOME_UNKNOWN" if code == 4 else "WINDOWS_BRIDGE_REFUSED", file=sys.stderr)
        return code
    except Exception:
        print("WINDOWS_BRIDGE_REFUSED", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
