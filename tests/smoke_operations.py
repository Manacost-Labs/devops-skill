#!/usr/bin/env python3
"""Disposable, isolated engine syntax and real promtool checks; no live targets."""
from __future__ import annotations

import argparse
import subprocess
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
# Official project image manifests resolved 2026-10-29. No floating tag at execution.
ENGINES = {
    "postgresql": ("postgres:18@sha256:979bccfde35445db618c65107d27d08c6c21339d8dc3ad4c830c6633947be0e4", "POSTGRES_HOST_AUTH_METHOD=trust", ["psql", "-X", "--username=postgres", "--dbname=postgres", "--set=ON_ERROR_STOP=1"]),
    "mysql": ("mysql:8.4@sha256:a0225d1ea6631c8bc2385dc4c2faba17bbf1834ecf369e1659a9a382bd8d5dd7", "MYSQL_ALLOW_EMPTY_PASSWORD=yes", ["mysql", "--no-defaults", "--protocol=socket", "--user=root", "--batch"]),
    "mariadb": ("mariadb:11.4@sha256:d1891ede5a559f1086f55053bb8cc1569b0298338c4d72d71725a7f74f6ba620", "MARIADB_ALLOW_EMPTY_ROOT_PASSWORD=1", ["mariadb", "--no-defaults", "--protocol=socket", "--user=root", "--batch"]),
}
PROMETHEUS = "prom/prometheus:v3.5.0@sha256:63805ebb8d2b3920190daf1cb14a60871b16fd38bed42b857a3182bc621f4996"


def run(argv, **kwargs):
    return subprocess.run(argv, capture_output=True, text=True, timeout=180, **kwargs)


def engine_smoke(engine):
    image, synthetic_auth, client = ENGINES[engine]
    name = "devops-syntax-" + uuid.uuid4().hex
    pulled = run(["docker", "pull", image])
    if pulled.returncode:
        raise RuntimeError(pulled.stderr)
    try:
        started = run(["docker", "run", "--detach", "--rm", "--network=none", "--memory=2g", "--cpus=2", "--name", name, "--env", synthetic_auth, image])
        if started.returncode:
            raise RuntimeError(started.stderr)
        for _ in range(90):
            # Entry points expose a temporary socket server during initialization.
            # Accept readiness only after PID 1 has exec'd the final database daemon.
            daemon = run(["docker", "exec", name, "cat", "/proc/1/comm"])
            probe = run(["docker", "exec", "-i", name, *client], input="SELECT 1;\n")
            expected_daemon = {"postgresql": "postgres", "mysql": "mysqld", "mariadb": "mariadbd"}[engine]
            if daemon.returncode == 0 and daemon.stdout.strip() == expected_daemon and probe.returncode == 0:
                break
            time.sleep(2)
        else:
            raise RuntimeError("engine startup did not reach local socket readiness")
        sql = (ROOT/f"database-operations/scripts/{engine}-diagnostics.sql").read_text(encoding="utf-8")
        result = run(["docker", "exec", "-i", name, *client], input=sql)
        if result.returncode:
            raise RuntimeError(result.stderr)
        expected = "server_version_num" if engine == "postgresql" else "engine_version"
        if expected not in result.stdout:
            raise RuntimeError("expected diagnostic result not returned")
        if engine in {"mysql", "mariadb"}:
            other = "mariadb" if engine == "mysql" else "mysql"
            wrong = (ROOT/f"database-operations/scripts/{other}-diagnostics.sql").read_text(encoding="utf-8")
            rejected = run(["docker", "exec", "-i", name, *client], input=wrong)
            if rejected.returncode == 0:
                raise RuntimeError("cross-vendor template unexpectedly accepted; review version boundary")
        print(f"OK: {engine} diagnostic SQL accepted on isolated baseline engine")
    finally:
        run(["docker", "rm", "--force", name])


def prometheus_smoke():
    folder = ROOT/"reliability-operations/templates"
    args = ["docker", "run", "--rm", "--network=none", "--memory=512m", "--cpus=2", "--entrypoint=/bin/promtool", "--mount", f"type=bind,source={folder},target=/rules,readonly", "--workdir=/rules", PROMETHEUS]
    for command in (["check", "rules", "prometheus-rules.yaml"], ["test", "rules", "prometheus-rule-tests.yaml"]):
        result = run([*args, *command])
        print(result.stdout)
        if result.returncode:
            raise RuntimeError(result.stderr)
    print("OK: real promtool rule validation and behavior tests")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("component", choices=[*ENGINES, "prometheus"])
    args = parser.parse_args()
    if args.component == "prometheus": prometheus_smoke()
    else: engine_smoke(args.component)


if __name__ == "__main__":
    main()
