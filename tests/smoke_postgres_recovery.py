#!/usr/bin/env python3
"""Actual PostgreSQL backup/WAL/PITR on disposable GitHub-hosted Linux only."""
from __future__ import annotations

import shutil
import time

from recovery_fixture import RecoveryFixture, require_native_rejection

# Official image index already used by operations syntax CI; resolved 2026-10-29.
IMAGE = "postgres:18@sha256:979bccfde35445db618c65107d27d08c6c21339d8dc3ad4c830c6633947be0e4"
SOCKET = ["psql", "-X", "--host=/fixture", "--username=postgres", "--dbname=postgres",
          "--no-align", "--tuples-only", "--set=ON_ERROR_STOP=1"]


def sql(fixture, identity, statement):
    return fixture.execute(identity, *SOCKET, input=statement).stdout.strip()


def check_data(fixture, identity, expected):
    result = sql(fixture, identity, "SELECT balance FROM accounts WHERE id=1; SELECT total FROM balances; SELECT count(*) FROM accounts;")
    if result.splitlines() != [str(expected), str(expected+200), "2"]:
        raise RuntimeError("PostgreSQL application invariants differ: "+result)


def start(fixture, identity, *, expected=0):
    return fixture.execute(identity, "pg_ctl", "-D", "/fixture/target", "-l", "/fixture/engine.log",
                           "-t", "20", "-w", "start", expected=expected, timeout=30)


def restore(fixture, base, archive=None, *, target="fixture_safe", negative=False):
    identity = fixture.engine(IMAGE, "postgres")
    fixture.import_tree(identity, base, "/fixture/target")
    # Verify original bytes before changing configuration. This is necessary, not restore proof.
    fixture.execute(identity, "pg_verifybackup", "/fixture/target")
    config = "listen_addresses=''\nunix_socket_directories='/fixture'\narchive_mode=off\narchive_command=''\n"
    if archive is not None:
        fixture.import_tree(identity, archive, "/fixture/archive")
        config += ("restore_command='cp /fixture/archive/%f %p'\n"
                   "recovery_target_timeline='1'\nrecovery_target_name='"+target+"'\n"
                   "recovery_target_action='"+("promote" if negative else "pause")+"'\n"
                   "hot_standby="+("off" if negative else "on")+"\n")
        fixture.write(identity, "/fixture/target/recovery.signal", "")
    fixture.write(identity, "/fixture/target/postgresql.auto.conf", config)
    return identity


UNREACHED = r"recovery ended before configured recovery target was reached"
INVALID_WAL = r"(incorrect size|invalid (?:magic|record)|incorrect.*checksum)"


def require_startup_failure(fixture, identity, reason, *, corrupt=False):
    result = start(fixture, identity, expected=None)
    status = fixture.execute(identity, "pg_ctl", "-D", "/fixture/target", "status", expected=None)
    if result.returncode == 0 or status.returncode == 0:
        raise RuntimeError(reason+" did not prevent completed recovery/startup")
    log = fixture.execute(identity, "cat", "/fixture/engine.log").stdout
    require_native_rejection(result.returncode, log, UNREACHED)
    if corrupt:
        require_native_rejection(result.returncode, log, INVALID_WAL)
    print("OK: PostgreSQL refuses "+reason)


def main():
    started = time.monotonic()
    with RecoveryFixture() as fixture:
        source = fixture.engine(IMAGE, "postgres")
        fixture.execute(source, "mkdir", "/fixture/archive")
        fixture.execute(source, "initdb", "-D", "/fixture/source", "--auth=trust", "--no-instructions",
                        "--data-checksums", "--wal-segsize=1")
        fixture.write(source, "/fixture/source/postgresql.auto.conf",
                      "listen_addresses=''\nunix_socket_directories='/fixture'\narchive_mode=on\n"
                      "archive_command='test ! -f /fixture/archive/%f && cp %p /fixture/archive/%f'\n")
        fixture.execute(source, "pg_ctl", "-D", "/fixture/source", "-l", "/fixture/source.log", "-w", "start")
        version = sql(fixture, source, "SHOW server_version_num;")
        if not version.isdecimal() or not 180000 <= int(version) < 190000:
            raise RuntimeError("PostgreSQL 18 engine required")
        print("PostgreSQL server_version_num="+version+" image="+IMAGE)
        for tool in ("pg_basebackup", "pg_verifybackup", "pg_waldump"):
            print(fixture.execute(source, tool, "--version").stdout.strip())
        sql(fixture, source, "CREATE TABLE accounts(id bigint PRIMARY KEY, balance bigint NOT NULL); INSERT INTO accounts VALUES(1,100),(2,200); CREATE VIEW balances AS SELECT sum(balance) AS total FROM accounts;")
        fixture.execute(source, "pg_basebackup", "-h", "/fixture", "-U", "postgres", "-D", "/fixture/base",
                        "--wal-method=stream", "--checkpoint=fast", "--manifest-checksums=SHA256")
        fixture.execute(source, "pg_verifybackup", "/fixture/base")
        base = fixture.export(source, "/fixture/base", "base")
        # A restore from the base alone has the original values.
        original = restore(fixture, base)
        start(fixture, original)
        check_data(fixture, original, 100)
        fixture.execute(original, "pg_ctl", "-D", "/fixture/target", "-m", "fast", "-w", "stop")
        print("OK: PostgreSQL physical base backup and native verified isolated restore")

        sql(fixture, source, "UPDATE accounts SET balance=150 WHERE id=1; SELECT pg_switch_wal(); UPDATE accounts SET balance=175 WHERE id=1;")
        safe_lsn = sql(fixture, source, "SELECT pg_create_restore_point('fixture_safe');")
        needed_wal = sql(fixture, source, "SELECT pg_walfile_name('"+safe_lsn+"');")
        sql(fixture, source, "UPDATE accounts SET balance=-999 WHERE id=1; SELECT pg_switch_wal();")
        check_data(fixture, source, -999)
        deadline = time.monotonic()+30
        while fixture.execute(source, "test", "-f", "/fixture/archive/"+needed_wal, expected=None).returncode:
            if time.monotonic() >= deadline:
                raise RuntimeError("required WAL did not reach archive")
            time.sleep(.2)
        archive = fixture.export(source, "/fixture/archive", "archive")
        recovered = restore(fixture, base, archive)
        start(fixture, recovered)
        deadline = time.monotonic()+30
        while sql(fixture, recovered, "SELECT pg_get_wal_replay_pause_state();") != "paused":
            if time.monotonic() >= deadline:
                raise RuntimeError("recovery did not pause at exact restore point")
            time.sleep(.2)
        check_data(fixture, recovered, 175)
        if sql(fixture, recovered, "SELECT pg_is_in_recovery();") != "t":
            raise RuntimeError("target did not remain quarantined in recovery")
        # Actual old process is stopped before the restored copy becomes writable.
        fixture.execute(source, "pg_ctl", "-D", "/fixture/source", "-m", "fast", "-w", "stop")
        if fixture.execute(source, "pg_ctl", "-D", "/fixture/source", "status", expected=None).returncode == 0:
            raise RuntimeError("old writer still running")
        sql(fixture, recovered, "SELECT pg_wal_replay_resume();")
        deadline = time.monotonic()+30
        while sql(fixture, recovered, "SELECT pg_is_in_recovery();") != "f":
            if time.monotonic() >= deadline:
                raise RuntimeError("restored target did not finish recovery")
            time.sleep(.2)
        sql(fixture, recovered, "CHECKPOINT;")
        if sql(fixture, recovered, "SELECT timeline_id FROM pg_control_checkpoint();") != "2":
            raise RuntimeError("promotion did not create a new timeline")
        check_data(fixture, recovered, 175)
        fixture.execute(recovered, "pg_ctl", "-D", "/fixture/target", "-m", "fast", "-w", "stop")
        print("OK: PostgreSQL multi-segment WAL replay includes wanted writes, excludes unwanted write, pauses and creates timeline 2 after fencing")

        control = restore(fixture, base, archive, negative=True)
        start(fixture, control)
        check_data(fixture, control, 175)
        if sql(fixture, control, "SELECT pg_is_in_recovery();") != "f":
            raise RuntimeError("negative-configuration healthy control did not complete recovery")
        fixture.execute(control, "pg_ctl", "-D", "/fixture/target", "-m", "fast", "-w", "stop")
        print("OK: healthy archive completes with the same promote/hot_standby=off configuration used by negative controls")

        missing = fixture.folder/"missing"
        shutil.copytree(archive, missing)
        (missing/needed_wal).unlink()
        require_startup_failure(fixture, restore(fixture, base, missing, negative=True), "missing required WAL")
        corrupt = fixture.folder/"corrupt"
        shutil.copytree(archive, corrupt)
        (corrupt/needed_wal).write_bytes(b"not PostgreSQL WAL")
        require_startup_failure(fixture, restore(fixture, base, corrupt, negative=True), "corrupt required WAL", corrupt=True)
        require_startup_failure(fixture, restore(fixture, base, archive, target="never_created", negative=True), "unreachable recovery target")
        broken = fixture.folder/"broken-base"
        shutil.copytree(base, broken)
        (broken/"PG_VERSION").write_text("19\n", encoding="ascii")
        validator = fixture.engine(IMAGE, "postgres")
        fixture.import_tree(validator, broken, "/fixture/target")
        rejected = fixture.execute(validator, "pg_verifybackup", "/fixture/target", expected=None)
        require_native_rejection(rejected.returncode, rejected.stdout+rejected.stderr, r'checksum mismatch.*PG_VERSION')
        print("OK: PostgreSQL native manifest verification rejects altered base bytes")
    print(f"OK: PostgreSQL synthetic recovery drill {time.monotonic()-started:.2f}s; no production RPO/RTO or HA certification")


if __name__ == "__main__":
    main()
