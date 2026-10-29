#!/usr/bin/env python3
"""Synthetic logical/PITR and MariaDB physical drills on isolated pinned engines."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import tempfile
import time
import uuid
from pathlib import Path

from smoke_operations import ENGINES, ROOT


def run(argv, *, input=None, timeout=180, check=True):
    result = subprocess.run(argv, input=input, capture_output=True, text=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f"command failed ({result.returncode}): {result.stderr[-2000:]}")
    return result


class Engine:
    def __init__(self, engine, *, sleeping=False):
        self.engine, self.image, self.auth, self.client = engine, *ENGINES[engine]
        self.name = "recovery-drill-" + uuid.uuid4().hex
        self.sleeping = sleeping

    def __enter__(self):
        # Pull exact reviewed manifests; no ports, host credentials or external network.
        run(["docker", "pull", self.image])
        args = ["docker", "run", "--detach", "--rm", "--network=none", "--memory=2g", "--cpus=2", "--name", self.name]
        if self.sleeping:
            run([*args, "--entrypoint=/bin/sleep", self.image, "infinity"])
        else:
            skip = "--skip-replica-start" if self.engine == "mysql" else "--skip-slave-start"
            run([*args, "--env", self.auth, self.image, "--server-id=51", "--log-bin=/var/lib/mysql/recovery-bin", "--binlog-format=ROW", "--event-scheduler=OFF", skip])
            self.ready()
        return self

    def __exit__(self, *exc):
        run(["docker", "rm", "--force", "--volumes", self.name], check=False)

    def execute(self, argv, *, input=None, check=True):
        return run(["docker", "exec", "-i", self.name, *argv], input=input, check=check)

    def sql(self, sql, *, check=True):
        return self.execute([*self.client, "--skip-column-names"], input=sql, check=check)

    def ready(self):
        deadline = time.monotonic() + 150
        while time.monotonic() < deadline:
            if self.sql("SELECT 1;", check=False).returncode == 0:
                return
            time.sleep(2)
        raise RuntimeError("isolated engine did not become ready")

    def point(self):
        sql = "SHOW BINARY LOG STATUS;" if self.engine == "mysql" else "SHOW MASTER STATUS;"
        values = self.sql(sql).stdout.strip().split("\t")
        if len(values) < 2 or not re.fullmatch(r"recovery-bin\.\d{6}", values[0]):
            raise RuntimeError("unexpected synthetic log identity")
        return values[0], int(values[1])


BASE = """
CREATE DATABASE recovery_fixture;
CREATE TABLE recovery_fixture.accounts(id INT PRIMARY KEY, balance INT NOT NULL) ENGINE=InnoDB;
CREATE TABLE recovery_fixture.audit(id INT AUTO_INCREMENT PRIMARY KEY, account_id INT) ENGINE=InnoDB;
INSERT INTO recovery_fixture.accounts VALUES (1,100),(2,200);
CREATE VIEW recovery_fixture.total_balance AS SELECT SUM(balance) AS total FROM recovery_fixture.accounts;
CREATE PROCEDURE recovery_fixture.read_total() SELECT total FROM recovery_fixture.total_balance;
CREATE TRIGGER recovery_fixture.account_audit AFTER UPDATE ON recovery_fixture.accounts FOR EACH ROW INSERT INTO recovery_fixture.audit(account_id) VALUES (NEW.id);
CREATE EVENT recovery_fixture.never_run ON SCHEDULE EVERY 1 DAY STARTS CURRENT_TIMESTAMP + INTERVAL 1 DAY DO INSERT INTO recovery_fixture.audit(account_id) VALUES (999);
"""


def assert_data(engine, balance, audit_count):
    values = engine.sql("SELECT balance FROM recovery_fixture.accounts WHERE id=1; SELECT COUNT(*) FROM recovery_fixture.audit; CALL recovery_fixture.read_total(); SELECT @@global.event_scheduler;").stdout.strip().splitlines()
    if values != [str(balance), str(audit_count), str(balance + 200), "OFF"]:
        raise RuntimeError("restored data/application/scheduler invariants differ: " + repr(values))
    objects = engine.sql("SELECT COUNT(*) FROM information_schema.TRIGGERS WHERE TRIGGER_SCHEMA='recovery_fixture'; SELECT COUNT(*) FROM information_schema.EVENTS WHERE EVENT_SCHEMA='recovery_fixture';").stdout.strip().splitlines()
    if objects != ["1", "1"]:
        raise RuntimeError("trigger/event inventory differs")


def logical_pitr(engine):
    with Engine(engine) as source, Engine(engine) as target, tempfile.TemporaryDirectory() as directory:
        source.sql(BASE)
        program = "mysqldump" if engine == "mysql" else "mariadb-dump"
        coordinate = "--source-data=2" if engine == "mysql" else "--master-data=2"
        options = [program, "--no-defaults", "--protocol=socket", "--user=root", "--single-transaction", "--quick", coordinate, "--routines", "--events", "--triggers", "--hex-blob"]
        if engine == "mysql": options += ["--no-tablespaces", "--set-gtid-purged=OFF"]
        dump = source.execute([*options, "--databases", "recovery_fixture"]).stdout
        match = re.search(r"(?:SOURCE|MASTER)_LOG_FILE\s*=\s*'(recovery-bin\.\d{6})'.*?(?:SOURCE|MASTER)_LOG_POS\s*=\s*(\d+)", dump)
        if not match:
            raise RuntimeError("consistent snapshot coordinate missing from dump")
        start = match.group(1), int(match.group(2))
        source.sql("UPDATE recovery_fixture.accounts SET balance=150 WHERE id=1; FLUSH BINARY LOGS; UPDATE recovery_fixture.accounts SET balance=175 WHERE id=1;")
        stop = source.point()  # complete safe transaction committed before unwanted work
        source.sql("UPDATE recovery_fixture.accounts SET balance=-999 WHERE id=1; FLUSH BINARY LOGS;")
        assert_data(source, -999, 3)
        if start[0] == stop[0]:
            raise RuntimeError("test did not cross a rotated binary log")
        files = [f"recovery-bin.{number:06d}" for number in range(int(start[0].split('.')[1]), int(stop[0].split('.')[1]) + 1)]
        artifacts = Path(directory)
        (artifacts/"base.sql").write_bytes(dump.encode())
        logs = []
        for name in files:
            run(["docker", "cp", f"{source.name}:/var/lib/mysql/{name}", str(artifacts/name)])
            content = (artifacts/name).read_bytes()
            logs.append({"name": name, "file": name, "size": len(content), "sha256": hashlib.sha256(content).hexdigest()})
        backup = (artifacts/"base.sql").read_bytes()
        receipt = {"schema_version": "1.0", "engine": engine, "source_ref": "inventory:synthetic-source", "coordinate_evidence_ref": "evidence:dump-coordinate", "boundary_evidence_ref": "evidence:before-unwanted-update", "backup": {"file": "base.sql", "size": len(backup), "sha256": hashlib.sha256(backup).hexdigest()}, "start": {"name": start[0], "position": start[1]}, "stop": {"name": stop[0], "position": stop[1]}, "logs": logs}
        receipt_file = artifacts/"receipt.json"
        receipt_file.write_text(json.dumps(receipt), encoding="utf-8")
        verifier = ROOT/"data-resilience-operations/scripts/verify-binlog-chain.py"
        run(["python", str(verifier), str(receipt_file), "--root", directory])
        target.sql(dump)
        assert_data(target, 100, 0)
        decoder = "mysqlbinlog" if engine == "mysql" else "mariadb-binlog"
        replay = source.execute([decoder, "--no-defaults", "--verify-binlog-checksum", f"--start-position={start[1]}", f"--stop-position={stop[1]}", *[f"/var/lib/mysql/{name}" for name in files]]).stdout
        target.sql(replay)  # one connection, no force or suppressed errors
        assert_data(target, 175, 2)
        # A missing archive segment and damaged bytes must fail, even though DB restore passed.
        first = artifacts/files[0]
        original = first.read_bytes()
        first.write_bytes(original[:-1])
        if run(["python", str(verifier), str(receipt_file), "--root", directory], check=False).returncode == 0:
            raise RuntimeError("truncated recovery log accepted")
        first.write_bytes(original)
        receipt["logs"] = receipt["logs"][1:]
        receipt_file.write_text(json.dumps(receipt), encoding="utf-8")
        if run(["python", str(verifier), str(receipt_file), "--root", directory], check=False).returncode == 0:
            raise RuntimeError("missing recovery log accepted")
        print(f"OK: {engine} logical restore + two-file PITR includes safe writes and excludes unwanted transaction")


def physical_mariadb():
    with Engine("mariadb") as source, Engine("mariadb", sleeping=True) as target, tempfile.TemporaryDirectory() as directory:
        source.sql(BASE)
        tool = ["mariadb-backup", "--no-defaults"]
        capture = ["--backup", "--user=root", "--socket=/run/mysqld/mysqld.sock", "--datadir=/var/lib/mysql"]
        source.execute([*tool, *capture, "--target-dir=/tmp/recovery-full"])
        source.sql("UPDATE recovery_fixture.accounts SET balance=175 WHERE id=1;")
        source.execute([*tool, *capture, "--target-dir=/tmp/recovery-inc", "--incremental-basedir=/tmp/recovery-full"])
        source.sql("UPDATE recovery_fixture.accounts SET balance=-999 WHERE id=1;")
        source.execute(["cp", "-a", "/tmp/recovery-full", "/tmp/recovery-prepared"])
        source.execute([*tool, "--prepare", "--target-dir=/tmp/recovery-prepared"])
        source.execute([*tool, "--prepare", "--target-dir=/tmp/recovery-prepared", "--incremental-dir=/tmp/recovery-inc"])
        # Stage into a running utility container; MariaDB itself is stopped throughout copy-back.
        folder = Path(directory)/"prepared"
        run(["docker", "cp", f"{source.name}:/tmp/recovery-prepared", str(folder)])
        run(["docker", "cp", str(folder), f"{target.name}:/tmp/recovery-prepared"])
        target.execute([*tool, "--copy-back", "--target-dir=/tmp/recovery-prepared", "--datadir=/var/lib/mysql"])
        target.execute(["chown", "-R", "mysql:mysql", "/var/lib/mysql"])
        run(["docker", "exec", "--detach", target.name, "mariadbd", "--no-defaults", "--user=mysql", "--datadir=/var/lib/mysql", "--socket=/tmp/recovery.sock", "--pid-file=/tmp/recovery.pid", "--log-error=/tmp/recovery-error.log", "--skip-networking", "--event-scheduler=OFF", "--skip-slave-start"])
        target.client = [*target.client, "--socket=/tmp/recovery.sock"]
        target.ready()
        assert_data(target, 175, 1)
        print("OK: MariaDB full + incremental backup, prepared work copy, empty-target copy-back and isolated data checks")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scenario", choices=["mysql", "mariadb", "mariadb-physical"])
    args = parser.parse_args()
    started = time.monotonic()
    if args.scenario == "mariadb-physical": physical_mariadb()
    else: logical_pitr(args.scenario)
    print(f"OK: synthetic drill elapsed {time.monotonic() - started:.2f}s; no production RPO/RTO claim")


if __name__ == "__main__":
    main()
