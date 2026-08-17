#!/usr/bin/env python3
"""Fail-closed PreToolUse hook that makes ungated mutation technically impossible.

The hook reads one Claude Code PreToolUse payload from stdin and decides whether
the proposed shell command may run:

- provably read-only commands are allowed;
- registered platform scripts are allowed after resolved-path verification;
- an invocation of ``tools/devops_exec.py`` is allowed only when the referenced
  operation request binds ``change.plan_digest`` to the canonical digest of the
  wrapped command, the execution window is currently open, and the registered
  operation gate returns a fresh PASS;
- every other command, including obfuscated or unclassifiable ones, is denied.

Unknown means mutating. Any parsing failure or internal error denies.
"""
from __future__ import annotations

import hashlib
import json
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "devops-platform-contracts" / "scripts" / "operation_gate.py"
WRAPPER = ROOT / "tools" / "devops_exec.py"
READ_ONLY_PLATFORM_SCRIPTS = {
    (ROOT / relative).resolve()
    for relative in (
        "devops-platform-contracts/scripts/validate_platform.py",
        "devops-platform-contracts/scripts/operation_gate.py",
        "devops-platform-contracts/scripts/resolve_capabilities.py",
        "devops-platform-contracts/scripts/ledger_chain.py",
        "devops-core/scripts/profile_digest.py",
        "devops-core/scripts/validate_contracts.py",
        "docker-operations/scripts/compose-preflight.py",
        "network-edge-operations/scripts/http-path-check.py",
        "reliability-operations/scripts/deploy-verify.py",
        "github-operations/scripts/repo-protection-audit.py",
        "examples/portfolio-demo/run_demo.py",
    )
}
OBFUSCATION_MARKERS = ("$(", "`", "${", "<(", ">(", "$")
SEPARATORS = {";", "&&", "||", "|", "&"}
PYTHON_NAMES = ("python", "python3", "python.exe", "python3.exe", "py", "py.exe")
SHELL_WRAPPERS = {
    "bash", "sh", "zsh", "dash", "ksh", "fish", "pwsh", "powershell", "cmd",
    "eval", "exec", "source", "xargs", "env", "nohup", "setsid", "watch",
    "base64", "perl", "ruby", "node", "awk", "sed",
}
SIMPLE_READ_ONLY = {
    "ls", "cat", "head", "tail", "pwd", "whoami", "id", "uname", "hostname",
    "date", "uptime", "df", "du", "free", "ps", "stat", "file", "wc", "which",
    "printenv", "echo", "grep", "sort", "uniq", "cut", "tr", "jq", "dig",
    "nslookup", "journalctl", "ss", "netstat", "findmnt", "lsblk", "true",
}
FIND_MUTATING_FLAGS = {"-delete", "-exec", "-execdir", "-ok", "-okdir", "-fprintf", "-fprint"}
SYSTEMCTL_READ_ONLY = {
    "status", "show", "cat", "is-active", "is-enabled", "is-failed", "is-system-running",
    "list-units", "list-unit-files", "list-timers", "list-dependencies", "list-sockets",
}
KUBECTL_READ_ONLY = {
    "get", "describe", "logs", "top", "version", "explain", "diff",
    "api-resources", "api-versions", "cluster-info",
}
TERRAFORM_READ_ONLY = {"plan", "validate", "show", "output", "version", "providers", "graph"}
DOCKER_READ_ONLY = {"ps", "images", "inspect", "logs", "version", "info", "stats", "port", "top"}
DOCKER_READ_ONLY_SUB = {
    "image": {"ls", "inspect", "history"},
    "container": {"ls", "inspect", "logs", "top", "stats", "port"},
    "network": {"ls", "inspect"},
    "volume": {"ls", "inspect"},
    "system": {"df", "events", "info"},
    "compose": {"ps", "config", "logs", "version"},
}
GIT_READ_ONLY = {"status", "log", "diff", "show", "rev-parse", "ls-files", "blame", "describe", "shortlog", "grep"}
HELM_READ_ONLY = {"list", "status", "get", "history", "show", "version"}
PACKAGE_READ_ONLY = {"list", "show", "search", "info", "check-update"}
AWS_READ_ONLY_OPERATION = re.compile(r"^(describe|list|get)-[a-z0-9-]+$")
AWS_MUTATING_OPERATION = re.compile(
    r"^(create|delete|update|put|attach|detach|modify|run|start|stop|terminate|reboot|associate|disassociate|"
    r"authorize|revoke|enable|disable|set|add|remove|tag|untag|import|restore|replace|register|deregister|"
    r"apply|cancel|execute|invoke|publish|purge|release|copy|move|reset|rotate|assume)(-[a-z0-9-]+)?$"
)
CLOUD_READ_ONLY_VERBS = {"describe", "list", "show", "get"}
CLOUD_MUTATING_VERBS = {
    "create", "delete", "update", "set", "add", "remove", "deploy", "apply", "patch", "enable",
    "disable", "start", "stop", "restart", "resize", "attach", "detach", "import", "export",
    "run", "submit", "rollout", "promote", "migrate", "reset", "rotate", "upgrade", "scale",
}
GH_READ_ONLY = {
    "pr": {"view", "list", "checks", "diff", "status"},
    "run": {"list", "view", "watch"},
    "repo": {"view", "list"},
    "release": {"list", "view"},
    "workflow": {"list", "view"},
    "ruleset": {"list", "view", "check"},
    "issue": {"list", "view"},
    "cache": {"list"},
    "label": {"list"},
    "auth": {"status"},
    "status": {""},
}
GH_API_MUTATING_FLAGS = ("-X", "--method", "-f", "--field", "-F", "--raw-field", "--input")
CURL_MUTATING_FLAGS = {
    "-d", "--data", "--data-raw", "--data-binary", "--data-urlencode", "-F", "--form",
    "-T", "--upload-file", "-o", "-O", "--output", "--remote-name", "-K", "--config",
}
REMEDIATION = (
    "run mutating work through 'python tools/devops_exec.py --operation <request.json> "
    "--policy <registered-policy> -- <command>' where change.plan_digest equals the canonical "
    "digest of the exact command argv and approvals plus the execution window are currently valid"
)


def canonical_command_digest(argv: list[str]) -> str:
    payload = json.dumps(list(argv), ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def decide(allow: bool, reason: str) -> int:
    decision = "allow" if allow else "deny"
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }))
    if not allow:
        print(reason, file=sys.stderr)
    return 0 if allow else 2


def command_name(token: str) -> str:
    name = token.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return name[:-4] if name.endswith(".exe") else name


def parse_rfc3339(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must carry a timezone")
    return parsed.astimezone(timezone.utc)


def resolve_script(token: str, cwd: Path) -> Path | None:
    candidate = Path(token.replace("\\", "/"))
    if not candidate.is_absolute():
        candidate = cwd / candidate
    try:
        return candidate.resolve(strict=True)
    except OSError:
        return None


def classify_python(argv: list[str], cwd: Path) -> tuple[bool, str]:
    if len(argv) < 2 or argv[1].startswith("-"):
        return False, "python may only run registered read-only platform scripts"
    resolved = resolve_script(argv[1], cwd)
    if resolved is not None and resolved in READ_ONLY_PLATFORM_SCRIPTS:
        return True, f"registered platform script {resolved.name}"
    return False, "python may only run registered read-only platform scripts"


def classify_segment(argv: list[str], cwd: Path) -> tuple[bool, str]:
    name = command_name(argv[0])
    rest = argv[1:]
    positionals = [token for token in rest if not token.startswith("-")]
    if name in SHELL_WRAPPERS:
        return False, f"'{name}' hides or transforms the real command"
    if name in SIMPLE_READ_ONLY:
        return True, name
    if name == "find":
        if any(token in FIND_MUTATING_FLAGS for token in rest):
            return False, "find with a mutating action flag"
        return True, "find"
    if name == "rg":
        if "--pre" in rest:
            return False, "rg --pre executes an external preprocessor"
        return True, "rg"
    if name in PYTHON_NAMES:
        return classify_python(argv, cwd)
    if name == "systemctl":
        verb = positionals[0] if positionals else ""
        return (verb in SYSTEMCTL_READ_ONLY, f"systemctl {verb}".strip())
    if name == "kubectl":
        verb = positionals[0] if positionals else ""
        if verb == "config":
            sub = positionals[1] if len(positionals) > 1 else ""
            return (sub in {"view", "get-contexts", "current-context", "get-clusters", "get-users"}, f"kubectl config {sub}")
        if verb == "auth":
            sub = positionals[1] if len(positionals) > 1 else ""
            return (sub == "can-i", f"kubectl auth {sub}")
        return (verb in KUBECTL_READ_ONLY, f"kubectl {verb}".strip())
    if name in {"terraform", "tofu"}:
        verb = positionals[0] if positionals else ""
        if verb == "fmt":
            return ("-check" in rest, f"{name} fmt")
        if verb == "state":
            sub = positionals[1] if len(positionals) > 1 else ""
            return (sub in {"list", "show"}, f"{name} state {sub}")
        return (verb in TERRAFORM_READ_ONLY, f"{name} {verb}".strip())
    if name == "docker":
        verb = positionals[0] if positionals else ""
        if verb in DOCKER_READ_ONLY_SUB:
            sub = positionals[1] if len(positionals) > 1 else ""
            return (sub in DOCKER_READ_ONLY_SUB[verb], f"docker {verb} {sub}")
        return (verb in DOCKER_READ_ONLY, f"docker {verb}".strip())
    if name == "git":
        verb = positionals[0] if positionals else ""
        return (verb in GIT_READ_ONLY, f"git {verb}".strip())
    if name == "helm":
        verb = positionals[0] if positionals else ""
        return (verb in HELM_READ_ONLY, f"helm {verb}".strip())
    if name in {"apt", "apt-get", "dnf", "yum", "apk", "zypper"}:
        verb = positionals[0] if positionals else ""
        return (verb in PACKAGE_READ_ONLY, f"{name} {verb}".strip())
    if name == "ip":
        if any(token in {"add", "del", "delete", "set", "flush", "replace", "change"} for token in rest):
            return False, "ip with a mutating subcommand"
        return True, "ip"
    if name == "aws":
        if any(AWS_MUTATING_OPERATION.fullmatch(token) for token in positionals):
            return False, "aws with a mutating operation"
        if any(AWS_READ_ONLY_OPERATION.fullmatch(token) for token in positionals):
            return True, "aws read-only operation"
        return False, "aws operation is not provably read-only"
    if name in {"gcloud", "gsutil", "az", "openstack"}:
        if any(token in CLOUD_MUTATING_VERBS for token in positionals):
            return False, f"{name} with a mutating verb"
        if any(token in CLOUD_READ_ONLY_VERBS for token in positionals):
            return True, f"{name} read-only verb"
        return False, f"{name} verb is not provably read-only"
    if name == "gh":
        verb = positionals[0] if positionals else ""
        if verb == "api":
            if any(token in GH_API_MUTATING_FLAGS or token.startswith(("--method", "--field", "--raw-field", "--input")) for token in rest):
                return False, "gh api with a mutating method or request body"
            return True, "gh api GET"
        sub = positionals[1] if len(positionals) > 1 else ""
        if sub in GH_READ_ONLY.get(verb, ()):
            return True, f"gh {verb} {sub}".strip()
        return False, f"gh {verb} {sub}".strip() + " is not provably read-only"
    if name == "curl":
        request_value = ""
        for index, token in enumerate(rest):
            if token in {"-X", "--request"}:
                request_value = rest[index + 1].upper() if index + 1 < len(rest) else "?"
        if request_value not in {"", "GET", "HEAD"}:
            return False, "curl with a non-GET request method"
        if any(token in CURL_MUTATING_FLAGS or token.startswith("--data") for token in rest):
            return False, "curl with upload, data, or output flags"
        return True, "curl read-only probe"
    return False, f"'{name}' is not classifiable as read-only"


def split_segments(tokens: list[str]) -> tuple[list[list[str]], str | None]:
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in SEPARATORS:
            segments.append([])
            continue
        if ">" in token or "<" in token:
            return [], f"redirection token '{token}' can write outside the approved plan"
        segments[-1].append(token)
    return [segment for segment in segments if segment], None


def is_wrapper(argv: list[str], cwd: Path) -> bool:
    if len(argv) < 2 or command_name(argv[0]) not in PYTHON_NAMES:
        return False
    resolved = resolve_script(argv[1], cwd)
    return resolved is not None and resolved == WRAPPER.resolve()


def verify_wrapper(argv: list[str], cwd: Path) -> tuple[bool, str]:
    arguments = argv[2:]
    if "--" not in arguments:
        return False, "wrapper invocation is missing the -- command separator"
    split = arguments.index("--")
    inner = arguments[split + 1 :]
    flags = arguments[:split]
    values: dict[str, str] = {}
    index = 0
    while index < len(flags):
        flag = flags[index]
        if not flag.startswith("--") or index + 1 >= len(flags):
            return False, f"wrapper flag '{flag}' is malformed"
        values[flag] = flags[index + 1]
        index += 2
    unknown = set(values) - {"--operation", "--policy", "--at", "--ledger", "--timeout-seconds"}
    if unknown:
        return False, "wrapper invocation carries unknown flags: " + ", ".join(sorted(unknown))
    if "--operation" not in values:
        return False, "wrapper invocation does not name an operation request"
    if not inner:
        return False, "wrapper invocation carries no command"
    operation_path = resolve_script(values["--operation"], cwd)
    if operation_path is None:
        return False, "wrapper operation request file does not exist"
    request = json.loads(operation_path.read_text(encoding="utf-8-sig"))
    if not isinstance(request, dict):
        return False, "wrapper operation request must be a JSON object"
    change = request.get("change")
    plan_digest = change.get("plan_digest") if isinstance(change, dict) else None
    digest = canonical_command_digest(inner)
    if plan_digest != digest:
        return False, f"approved plan digest does not match the canonical digest {digest} of the wrapped command"
    execution = request.get("execution")
    if not isinstance(execution, dict):
        return False, "wrapper operation request has no execution window"
    now = parse_rfc3339(values["--at"]) if "--at" in values else datetime.now(timezone.utc)
    window_start = parse_rfc3339(str(execution.get("window_start")))
    window_end = parse_rfc3339(str(execution.get("window_end")))
    if not window_start <= now <= window_end:
        return False, "execution window is not currently open"
    gate_arguments = [sys.executable, str(GATE), "--request", str(operation_path), "--policy", values.get("--policy", "default-policy.json")]
    if "--at" in values:
        gate_arguments += ["--at", values["--at"]]
    gate = subprocess.run(gate_arguments, capture_output=True, text=True, check=False)
    if gate.returncode != 0 or not gate.stdout.startswith("ALLOWED:"):
        return False, "operation gate did not return a fresh PASS: " + (gate.stdout + gate.stderr).strip()[:400]
    return True, "fresh gate PASS is bound to the exact wrapped command digest"


def evaluate(payload: dict) -> tuple[bool, str]:
    tool_name = payload.get("tool_name")
    if tool_name != "Bash":
        return True, f"tool {tool_name!r} is governed by allowed-tools declarations, not by the command gate"
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    if not isinstance(command, str) or not command.strip():
        return False, "BLOCKED: no shell command was provided"
    cwd_value = payload.get("cwd")
    cwd = Path(cwd_value) if isinstance(cwd_value, str) and cwd_value else ROOT
    if "\n" in command or "\r" in command:
        return False, "BLOCKED: multi-line commands cannot be verified against an approved plan"
    for marker in OBFUSCATION_MARKERS:
        if marker in command:
            return False, f"BLOCKED: '{marker}' can substitute or expand a hidden command; approve the literal command instead"
    tokens = shlex.split(command, posix=True)
    if not tokens:
        return False, "BLOCKED: empty command"
    segments, split_error = split_segments(tokens)
    if split_error:
        return False, f"BLOCKED: {split_error}"
    if not segments:
        return False, "BLOCKED: empty command"
    if len(segments) == 1 and is_wrapper(segments[0], cwd):
        verified, detail = verify_wrapper(segments[0], cwd)
        return (verified, ("ALLOWED: " if verified else "BLOCKED: ") + detail)
    for segment in segments:
        read_only, detail = classify_segment(segment, cwd)
        if not read_only:
            return False, f"BLOCKED: {detail}; {REMEDIATION}"
    return True, "ALLOWED: every command segment is provably read-only"


def main() -> int:
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            return decide(False, "BLOCKED: hook payload must be a JSON object")
        allow, reason = evaluate(payload)
        return decide(allow, reason)
    except Exception as error:  # fail closed on anything unexpected
        return decide(False, f"BLOCKED: hook could not verify the command ({type(error).__name__}: {error})")


if __name__ == "__main__":
    raise SystemExit(main())
