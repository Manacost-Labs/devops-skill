#!/usr/bin/env python3
"""Conservative command gate; requires a trusted runtime, PATH and CLI configuration."""
from __future__ import annotations
import hashlib, json, re, shlex, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "devops-platform-contracts/scripts/operation_gate.py"
WRAPPER = ROOT / "tools/devops_exec.py"
PLANNER = ROOT / "tools/devops_plan.py"
LEDGER_TOOL = ROOT / "devops-platform-contracts/scripts/ledger_chain.py"
READ_ONLY_PLATFORM_SCRIPTS = {
    (ROOT / relative).resolve() for relative in (
        "devops-platform-contracts/scripts/validate_platform.py",
        "devops-platform-contracts/scripts/operation_gate.py",
        "devops-platform-contracts/scripts/resolve_capabilities.py",
        "devops-core/scripts/profile_digest.py", "devops-core/scripts/validate_contracts.py",
        "docker-operations/scripts/compose-preflight.py",
        "network-edge-operations/scripts/http-path-check.py",
        "reliability-operations/scripts/deploy-verify.py",
        "github-operations/scripts/repo-protection-audit.py",
    )
}
PYTHON_NAMES = {"python", "python3", "python.exe", "python3.exe", "py", "py.exe"}
READ_TOOLS = {"Read", "Grep", "Glob", "Skill", "AskUserQuestion"}
REMEDIATION = "use tools/devops_exec.py with an exact, currently approved command for work outside the inspection grammar"
# Unknown, abbreviated and attached short options fail closed. Long options may
# use --name=value. These rules bound convenience reads; they are not a sandbox.
INSPECTION = {
    "ls": ("alhAFd1rt", {}, {"--all", "--human-readable"}),
    "cat": ("nbsEvT", {}, {"--number", "--show-all"}),
    "head": ("qv", {"-n": 1, "--lines": 1, "-c": 1, "--bytes": 1}, set()),
    "tail": ("qv", {"-n": 1, "--lines": 1, "-c": 1, "--bytes": 1}, set()),
    "pwd": ("LP", {}, set()), "whoami": ("", {}, set()),
    "id": ("ugGnrz", {}, set()), "uname": ("asnrvmpio", {}, {"--all"}),
    "hostname": ("fisd", {}, {"--fqdn", "--short", "--ip-address"}),
    "date": ("u", {}, {"--utc"}), "uptime": ("ps", {}, set()),
    "true": ("", {}, set()), "df": ("hTik", {}, {"--human-readable"}),
    "du": ("hsc", {"--max-depth": 1}, {"--human-readable"}),
    "free": ("hmg", {}, {"--human"}), "ps": ("auxef", {}, set()),
    "stat": ("L", {"-c": 1, "--format": 1}, set()),
    "file": ("biL", {}, {"--brief", "--mime"}), "wc": ("lwmcL", {}, {"--lines", "--words", "--bytes"}),
    "which": ("a", {}, set()), "echo": ("neE", {}, set()),
    "grep": ("EinvrlwocFs", {"-e": 1, "--regexp": 1, "-m": 1, "--max-count": 1}, {"--line-number", "--ignore-case", "--fixed-strings"}),
    "sort": ("nruhfV", {"-k": 1, "-t": 1}, {"--numeric-sort", "--reverse", "--unique"}),
    "uniq": ("cdu", {}, set()), "cut": ("s", {"-d": 1, "-f": 1, "-c": 1}, set()),
    "tr": ("dsc", {}, set()), "jq": ("rcseMS", {}, {"--raw-output", "--compact-output", "--slurp", "--exit-status"}),
    "rg": ("inlFsw", {"-e": 1, "--regexp": 1, "-m": 1, "--max-count": 1}, {"--files", "--hidden", "--line-number", "--ignore-case", "--fixed-strings", "--no-ignore"}),
    "journalctl": ("rqb", {"-u": 1, "--unit": 1, "-n": 1, "--lines": 1, "--since": 1, "--until": 1, "-o": 1, "--output": 1}, {"--no-pager", "--utc", "--list-boots", "--disk-usage"}),
    "ss": ("tulnpax", {}, set()), "netstat": ("tulnpax", {}, set()),
    "findmnt": ("", {"-o": 1, "--output": 1}, {"--json", "--list"}),
    "lsblk": ("af", {"-o": 1, "--output": 1}, {"--json"}),
}
GH_READ_ONLY = {
    "pr": {"view", "list", "checks", "diff", "status"}, "run": {"list", "view"},
    "repo": {"view", "list"}, "release": {"list", "view"}, "workflow": {"list", "view"},
    "ruleset": {"list", "view", "check"}, "issue": {"list", "view"},
    "cache": {"list"}, "label": {"list"}, "auth": {"status"},
}

def canonical_command_digest(argv):
    return "sha256:" + hashlib.sha256(json.dumps(argv, ensure_ascii=False, separators=(",", ":")).encode("utf-8")).hexdigest()

def decide(allow, reason):
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
        "permissionDecision": "allow" if allow else "deny", "permissionDecisionReason": reason}}))
    if not allow:
        print(reason, file=sys.stderr)
    return 0 if allow else 2

def parse_rfc3339(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("timestamp must carry a timezone")
    return parsed.astimezone(timezone.utc)

def resolve_script(token, cwd):
    path = Path(token.replace("\\", "/"))
    return (path if path.is_absolute() else cwd / path).resolve()

def python_script(argv, cwd):
    if len(argv) < 2:
        return None
    executable = argv[0].replace("\\", "/")
    if "/" in executable:
        if Path(executable).resolve() != Path(sys.executable).resolve():
            return None
    elif executable not in PYTHON_NAMES:
        return None
    if argv[1].startswith("-"):
        return None
    return resolve_script(argv[1], cwd)

def safe_options(arguments, short="", values=None, switches=()):
    """Return positionals, or None for an option outside this exact grammar."""
    values = values or {}
    positional = []
    index = 0
    while index < len(arguments):
        token = arguments[index]
        if token == "--":
            positional.extend(arguments[index + 1:])
            break
        key, equal, value = token.partition("=")
        if key in values:
            count = values[key]
            if equal:
                if not key.startswith("--") or count != 1 or not value:
                    return None
            else:
                if index + count >= len(arguments) or any(not item or item.startswith("-") for item in arguments[index + 1:index + count + 1]):
                    return None
                index += count
        elif token in switches:
            pass
        elif token.startswith("-") and token != "-":
            if token.startswith("--") or not short or any(letter not in short for letter in token[1:]):
                return None
        else:
            positional.append(token)
        index += 1
    return positional

def classify_segment(argv, cwd):
    name, rest = argv[0], argv[1:]
    script = python_script(argv, cwd)
    if script:
        if script in READ_ONLY_PLATFORM_SCRIPTS:
            return True, "registered inspection script"
        if script == LEDGER_TOOL.resolve():
            return len(rest) == 3 and rest[1] == "verify", "only ledger verification is an inspection"
        if script == PLANNER.resolve():
            outer = argv[2:argv.index("--")] if "--" in argv else argv[2:]
            outputs = []
            for index, token in enumerate(outer):
                if token == "--output":
                    if index + 1 >= len(outer):
                        return False, "planner output path is missing"
                    outputs.append(outer[index + 1])
                elif token.startswith("--output="):
                    outputs.append(token.split("=", 1)[1])
            if len(outputs) > 1:
                return False, "duplicate planner output"
            if outputs:
                output = resolve_script(outputs[0], cwd)
                allowed = ROOT.resolve() / "operations" / "plans"
                if allowed not in output.parents or output.suffix != ".json":
                    return False, "planner output must stay under runtime operations/plans with a .json suffix"
            return True, "planner cannot authorize execution"
        return False, "unregistered Python script"
    if "/" in name or "\\" in name:
        return False, "explicit executable paths require the wrapper"
    if name in INSPECTION:
        short, values, switches = INSPECTION[name]
        positional = safe_options(rest, short, values, switches)
        if positional is None:
            return False, f"{name} option is outside the inspection grammar"
        if name == "hostname" and positional:
            return False, "hostname arguments can change the hostname"
        if name == "uniq" and len(positional) > 1:
            return False, "uniq's second operand is an output file"
        if name == "date" and any(not item.startswith("+") for item in positional):
            return False, "date arguments can change the clock"
        return True, name
    if name == "systemctl":
        return (bool(rest) and rest[0] in {"status", "show", "cat", "is-active", "is-enabled", "is-failed", "list-units", "list-unit-files", "list-timers"}
            and safe_options(rest[1:], switches={"--no-pager", "--all", "--user", "--system", "--failed"}) is not None), "systemctl inspection"
    if name == "kubectl":
        return (bool(rest) and rest[0] in {"get", "describe", "logs", "top", "version", "explain", "api-resources", "api-versions"}
            and safe_options(rest[1:], "A", {"--output": 1, "-o": 1, "--namespace": 1, "-n": 1, "--context": 1, "--tail": 1, "-c": 1, "--container": 1}, {"--all-namespaces", "--previous", "--short"}) is not None), "kubectl inspection"
    if name in {"terraform", "tofu"}:
        return rest == ["version"], "provider execution and plan output require the wrapper"
    if name == "docker":
        route = 2 if rest and rest[0] in {"compose", "image", "container", "network", "volume", "system"} else 1
        command = tuple(rest[:route])
        allowed = {("ps",), ("images",), ("inspect",), ("logs",), ("version",), ("info",), ("top",),
            ("compose", "ps"), ("compose", "config"), ("compose", "logs"), ("compose", "version"),
            ("image", "ls"), ("image", "inspect"), ("container", "ls"), ("container", "inspect"),
            ("network", "ls"), ("network", "inspect"), ("volume", "ls"), ("volume", "inspect"), ("system", "df")}
        return command in allowed and safe_options(rest[route:], "aq", {"--tail": 1, "--format": 1}, {"--all", "--no-trunc", "--services", "--images"}) is not None, "docker inspection"
    if name == "git":
        return (bool(rest) and rest[0] in {"status", "log", "diff", "show", "rev-parse", "ls-files", "blame", "describe", "shortlog", "grep"}
            and safe_options(rest[1:], "sp", {"-n": 1, "--max-count": 1, "--format": 1}, {"--short", "--oneline", "--stat", "--name-only", "--no-ext-diff", "--no-textconv", "--cached", "--staged"}) is not None), "git inspection"
    if name == "aws":
        return (len(rest) >= 2 and not rest[0].startswith("-") and re.fullmatch(r"(describe|list)-[a-z0-9-]+", rest[1]) is not None
            and safe_options(rest[2:], values={"--region": 1, "--profile": 1, "--query": 1, "--output": 1}, switches={"--no-cli-pager", "--no-paginate"}) == []), "bounded AWS describe/list"
    if name in {"gcloud", "az"}:
        prefix = ["compute", "instances", "list"] if name == "gcloud" else ["vm", "show"]
        return (rest[:len(prefix)] == prefix and safe_options(rest[len(prefix):], values={"--name": 1, "--project": 1, "--zone": 1, "--resource-group": 1, "--subscription": 1, "--format": 1, "--query": 1, "--output": 1}) == []), "bounded cloud inspection"
    if name == "gh":
        if rest and rest[0] == "api":
            positional = safe_options(rest[1:], values={"--hostname": 1, "--jq": 1, "--template": 1}, switches={"--paginate", "--slurp", "--include"})
            return positional is not None and len(positional) == 1 and positional[0].startswith("repos/"), "GitHub repository GET without a body or method override"
        return (len(rest) >= 2 and rest[1] in GH_READ_ONLY.get(rest[0], ())
            and safe_options(rest[2:], values={"--repo": 1, "-R": 1, "--limit": 1, "--json": 1, "--jq": 1, "--branch": 1}, switches={"--log", "--log-failed"}) is not None), "GitHub inspection"
    if name == "curl":
        positional = safe_options(rest[1:], "IsS", {"--max-time": 1, "--connect-timeout": 1}, {"--head", "--silent", "--show-error", "--fail"})
        return (bool(rest) and rest[0] in {"-q", "--disable"} and positional is not None and len(positional) == 1
            and positional[0].startswith(("https://", "http://"))), "curl needs -q first, one HTTP URL and inspection-only options"
    return False, f"{name!r} is outside the inspection grammar"

def verify_wrapper(argv, cwd):
    arguments = argv[2:]
    if "--" not in arguments:
        return False, "wrapper is missing the -- command separator"
    split = arguments.index("--")
    flags, inner = arguments[:split], arguments[split + 1:]
    values = {}
    if not inner or len(flags) % 2:
        return False, "wrapper arguments are malformed"
    for index in range(0, len(flags), 2):
        flag = flags[index]
        if flag not in {"--operation", "--policy", "--ledger", "--timeout-seconds"} or flag in values:
            return False, f"unknown or duplicate wrapper flag: {flag}"
        values[flag] = flags[index + 1]
    if "--operation" not in values:
        return False, "operation request is missing"
    if "--ledger" in values:
        ledger = resolve_script(values["--ledger"], cwd)
        if ROOT.resolve() / "operations" not in ledger.parents or ledger.suffix != ".jsonl":
            return False, "protected ledger must stay under runtime operations with a .jsonl suffix"
    if "--timeout-seconds" in values and (not values["--timeout-seconds"].isdigit() or int(values["--timeout-seconds"]) < 1):
        return False, "timeout must be a positive integer"
    operation_path = resolve_script(values["--operation"], cwd)
    request = json.loads(operation_path.read_text(encoding="utf-8-sig"))
    if not isinstance(request, dict) or not isinstance(request.get("change"), dict):
        return False, "operation request has no change"
    if request["change"].get("plan_digest") != canonical_command_digest(inner):
        return False, "approved plan digest does not match the canonical digest of the wrapped command"
    execution = request.get("execution")
    if not isinstance(execution, dict):
        return False, "operation request has no execution window"
    now = datetime.now(timezone.utc)
    if not parse_rfc3339(str(execution.get("window_start"))) <= now <= parse_rfc3339(str(execution.get("window_end"))):
        return False, "execution window is not currently open"
    gate = subprocess.run([sys.executable, str(GATE), "--request", str(operation_path), "--policy", values.get("--policy", "default-policy.json")], capture_output=True, text=True, check=False)
    if gate.returncode or not gate.stdout.startswith("ALLOWED:"):
        return False, "operation gate did not return a fresh PASS: " + (gate.stdout + gate.stderr).strip()[:400]
    return True, "fresh gate PASS is bound to the exact wrapped command digest"

def evaluate(payload):
    tool = payload.get("tool_name")
    if tool != "Bash":
        return (True, "inspection/interaction tool") if tool in READ_TOOLS else (False, "BLOCKED: direct file edits, alternate shells and unregistered tools are outside this protected session")
    inputs = payload.get("tool_input")
    command = inputs.get("command") if isinstance(inputs, dict) else None
    if not isinstance(command, str) or not command.strip():
        return False, "BLOCKED: no shell command was provided"
    if any(character in command for character in "\n\r$*?[]{}" + chr(96)):
        return False, "BLOCKED: shell expansion or multi-line input requires the wrapper"
    lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|<>()")
    lexer.whitespace_split = True
    lexer.commenters = ""
    tokens = list(lexer)
    if not tokens:
        return False, "BLOCKED: empty command"
    # A tilde inside a Windows 8.3 path (RUNNER~1) is literal. Bash home
    # expansion begins a word; refuse that form, including conservative quotes.
    if any(token.startswith("~") for token in tokens):
        return False, "BLOCKED: home expansion requires a literal absolute path"
    if any(("<" in token or ">" in token) or (token != "|" and all(character in ";&|<>()" for character in token)) for token in tokens):
        return False, "BLOCKED: control operators, subshells and redirection require an approved literal command"
    segments = [[]]
    for token in tokens:
        if token == "|":
            if not segments[-1]:
                return False, "BLOCKED: empty pipeline segment"
            segments.append([])
        else:
            segments[-1].append(token)
    if not segments[-1]:
        return False, "BLOCKED: empty pipeline segment"
    cwd = Path(payload["cwd"]) if isinstance(payload.get("cwd"), str) else ROOT
    if len(segments) == 1 and python_script(segments[0], cwd) == WRAPPER.resolve():
        allowed, detail = verify_wrapper(segments[0], cwd)
        return allowed, ("ALLOWED: " if allowed else "BLOCKED: ") + detail
    for segment in segments:
        allowed, detail = classify_segment(segment, cwd)
        if not allowed:
            return False, f"BLOCKED: {detail}; {REMEDIATION}"
    return True, "ALLOWED: every segment matches the bounded inspection grammar"

def main():
    try:
        payload = json.loads(sys.stdin.read())
        if not isinstance(payload, dict):
            return decide(False, "BLOCKED: hook payload must be a JSON object")
        return decide(*evaluate(payload))
    except Exception as error:
        return decide(False, f"BLOCKED: hook could not verify input ({type(error).__name__})")

if __name__ == "__main__":
    raise SystemExit(main())
