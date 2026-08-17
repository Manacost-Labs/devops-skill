#!/usr/bin/env python3
"""Read-only Compose policy check; requires PyYAML."""
from __future__ import annotations
import re, sys
from pathlib import Path
import yaml

BAD_KEY = re.compile(r"(token|password|secret|api[_-]?key|private[_-]?key)", re.I)
SAFE_REFERENCE = re.compile(r"^(\$\{[A-Za-z_][A-Za-z0-9_]*(?::[-?][^}]*)?\}|/run/secrets/[^\s]+|(?:vault|ref|secret):[^\s]+)$")
SENSITIVE_BINDS = ("/", "/etc", "/proc", "/sys", "/dev", "/var/run", "/root", "/home")

def environment_items(value):
    if isinstance(value, dict): return value.items()
    if isinstance(value, list):
        parsed = []
        for item in value:
            key, separator, content = str(item).partition("=")
            parsed.append((key, content if separator else None))
        return parsed
    return []

def source_of_mount(value):
    if isinstance(value, str): return value.split(":", 1)[0]
    if isinstance(value, dict) and value.get("type") == "bind": return str(value.get("source", ""))
    return ""

def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: compose-preflight.py <compose.yaml>"); return 2
    path = Path(sys.argv[1])
    try: data = yaml.safe_load(path.read_text(encoding="utf-8-sig")) or {}
    except (OSError, yaml.YAMLError) as err: print(f"ERROR: {err}"); return 2
    services = data.get("services")
    if not isinstance(services, dict) or not services:
        print("ERROR: Compose file has no services mapping."); return 1
    errors, warnings = [], []
    for name, service in services.items():
        if not isinstance(service, dict): errors.append(f"{name}: service must be a mapping"); continue
        image = str(service.get("image", ""))
        if image.endswith(":latest") or image == "": errors.append(f"{name}: pin an explicit non-latest image")
        elif "@sha256:" not in image: warnings.append(f"{name}: image is not digest-pinned")
        if service.get("privileged") is True: errors.append(f"{name}: privileged mode requires redesign/explicit exception")
        if service.get("network_mode") == "host": errors.append(f"{name}: host networking requires explicit exception")
        if service.get("pid") == "host" or service.get("ipc") == "host": errors.append(f"{name}: host PID/IPC namespace requires redesign/explicit exception")
        if service.get("devices"): errors.append(f"{name}: host device access requires explicit exception")
        capabilities = {str(item).upper() for item in service.get("cap_add", []) or []}
        if capabilities & {"ALL", "SYS_ADMIN", "SYS_PTRACE", "NET_ADMIN", "DAC_READ_SEARCH"}: errors.append(f"{name}: high-risk Linux capabilities declared: {sorted(capabilities)}")
        mounts = service.get("volumes", []) or []
        if any("docker.sock" in str(v).lower() for v in mounts): errors.append(f"{name}: Docker socket mount requires explicit exception")
        for mount in mounts:
            source = source_of_mount(mount).replace("\\", "/").rstrip("/") or "/"
            if source in SENSITIVE_BINDS: errors.append(f"{name}: sensitive host bind mount {source} requires redesign/explicit exception")
        if "healthcheck" not in service: warnings.append(f"{name}: no healthcheck declared")
        if service.get("read_only") is not True: warnings.append(f"{name}: root filesystem is not read-only")
        if not service.get("user"): warnings.append(f"{name}: runtime user is not declared")
        security_opt = {str(item).lower() for item in service.get("security_opt", []) or []}
        if "no-new-privileges:true" not in security_opt: warnings.append(f"{name}: no-new-privileges is not enabled")
        for port in service.get("ports", []) or []:
            rendered = str(port)
            if rendered.startswith(("127.0.0.1:", "[::1]:")): warnings.append(f"{name}: loopback port published; confirm edge ownership")
            else: errors.append(f"{name}: potentially public port publication requires edge approval: {rendered}")
        env = service.get("environment", {})
        if not isinstance(env, (dict, list)): errors.append(f"{name}: environment must be a mapping or list")
        for key, value in environment_items(env):
            if BAD_KEY.search(str(key)) and value not in (None, "") and not SAFE_REFERENCE.match(str(value)):
                errors.append(f"{name}: literal sensitive environment value for {key}")
    for item in warnings: print(f"WARN: {item}")
    for item in errors: print(f"ERROR: {item}")
    if errors: return 1
    print(f"OK: {path} passed Compose safety preflight ({len(warnings)} warning(s)).")
    return 0
if __name__ == "__main__": raise SystemExit(main())
