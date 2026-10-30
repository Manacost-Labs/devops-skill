#!/usr/bin/env python3
"""Actual Redis RDB/multipart-AOF restore and refusal drills, never live targets."""
from __future__ import annotations

import re
import shutil
import time

from recovery_fixture import RecoveryFixture

# Official library/redis 7.4 multiarch index resolved 2026-10-30, never a floating pull.
IMAGE = "redis:7.4@sha256:b6b6e3dc0c0952737748e55d5d885272840c7e42ba41ab1d5489f693419882f5"


def cli(fixture, identity, *arguments, expected=0):
    return fixture.execute(identity, "redis-cli", "--raw", "-s", "/fixture/redis.sock",
                           *arguments, expected=expected).stdout.strip()


def start(fixture, identity, path, *, aof, expected=0, background=True):
    return fixture.execute(identity, "redis-server", "--port", "0", "--unixsocket", "/fixture/redis.sock",
                           "--unixsocketperm", "700", "--dir", path, "--dbfilename", "dump.rdb",
                           "--save", "", "--appendonly", "yes" if aof else "no",
                           "--appendfsync", "always", "--aof-load-truncated", "no",
                           "--auto-aof-rewrite-percentage", "0", "--daemonize", "yes" if background else "no",
                           "--logfile", "/fixture/engine.log", "--pidfile", "/fixture/redis.pid",
                           expected=expected)


def ready(fixture, identity):
    deadline = time.monotonic()+20
    while cli(fixture, identity, "PING", expected=None) != "PONG":
        if time.monotonic() >= deadline:
            raise RuntimeError("isolated Redis did not load the selected persistence artifact")
        time.sleep(.2)


def assert_data(fixture, identity, value, events, expiry):
    actual = [cli(fixture, identity, "GET", "account:1"),
              cli(fixture, identity, "GET", "account:2"),
              cli(fixture, identity, "HGET", "metadata", "generation"),
              cli(fixture, identity, "LRANGE", "events", "0", "-1"),
              cli(fixture, identity, "PEXPIRETIME", "transient"),
              cli(fixture, identity, "DBSIZE")]
    if actual != [str(value), "200", "before", "\n".join(events), expiry, "5"]:
        raise RuntimeError("Redis application/expiry invariants differ: "+repr(actual))
    if int(cli(fixture, identity, "PTTL", "transient")) <= 0:
        raise RuntimeError("fixture expired unexpectedly")


def check_rejected(fixture, source, *, aof, validator, reason):
    identity = fixture.engine(IMAGE, "redis")
    fixture.import_tree(identity, source, "/fixture/restore")
    if fixture.execute(identity, *validator, expected=None).returncode == 0:
        raise RuntimeError("native validator accepted "+reason)
    # Foreground load must terminate nonzero; a daemon fork acknowledgement is not proof.
    result = start(fixture, identity, "/fixture/restore", aof=aof, expected=None, background=False)
    if result.returncode == 0 or cli(fixture, identity, "PING", expected=None) == "PONG":
        raise RuntimeError("server loaded "+reason)
    print("OK: Redis native validation and startup reject "+reason)


def main():
    started = time.monotonic()
    with RecoveryFixture() as fixture:
        source = fixture.engine(IMAGE, "redis")
        fixture.execute(source, "mkdir", "/fixture/source")
        start(fixture, source, "/fixture/source", aof=True)
        ready(fixture, source)
        info = cli(fixture, source, "INFO", "server")
        if not re.search(r"(?m)^redis_version:7\.4\.", info):
            raise RuntimeError("Redis 7.4 baseline required")
        cli(fixture, source, "MSET", "account:1", "100", "account:2", "200")
        cli(fixture, source, "HSET", "metadata", "generation", "before")
        cli(fixture, source, "RPUSH", "events", "before")
        cli(fixture, source, "SET", "transient", "present", "PX", "600000")
        expiry = cli(fixture, source, "PEXPIRETIME", "transient")
        cli(fixture, source, "SAVE")  # bounded synthetic capture; not a production SAVE recommendation
        cli(fixture, source, "BGREWRITEAOF")
        deadline = time.monotonic()+30
        while True:
            persistence = cli(fixture, source, "INFO", "persistence")
            if ("aof_rewrite_in_progress:0" in persistence and "aof_rewrite_scheduled:0" in persistence
                    and "aof_last_bgrewrite_status:ok" in persistence):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError("AOF rewrite did not complete")
            time.sleep(.2)
        cli(fixture, source, "SET", "account:1", "175")
        cli(fixture, source, "RPUSH", "events", "wanted")
        assert_data(fixture, source, 175, ["before", "wanted"], expiry)
        cli(fixture, source, "SHUTDOWN", "NOSAVE")
        backup = fixture.export(source, "/fixture/source", "safe-backup")
        manifests = list((backup/"appendonlydir").glob("*.manifest"))
        base_files = list((backup/"appendonlydir").glob("*.base.rdb"))
        incrementals = list((backup/"appendonlydir").glob("*.incr.aof"))
        if len(manifests) != 1 or len(base_files) != 1 or len(incrementals) != 1 or incrementals[0].stat().st_size == 0:
            raise RuntimeError("expected actual multipart AOF base, incremental and manifest")
        start(fixture, source, "/fixture/source", aof=True)
        ready(fixture, source)
        cli(fixture, source, "SET", "account:1", "-999")
        cli(fixture, source, "RPUSH", "events", "unwanted")
        assert_data(fixture, source, -999, ["before", "wanted", "unwanted"], expiry)
        cli(fixture, source, "SHUTDOWN", "NOSAVE")

        rdb = fixture.folder/"rdb-only"
        rdb.mkdir()
        shutil.copyfile(backup/"dump.rdb", rdb/"dump.rdb")
        rdb_target = fixture.engine(IMAGE, "redis")
        fixture.import_tree(rdb_target, rdb, "/fixture/restore")
        fixture.execute(rdb_target, "redis-check-rdb", "/fixture/restore/dump.rdb")
        start(fixture, rdb_target, "/fixture/restore", aof=False)
        ready(fixture, rdb_target)
        assert_data(fixture, rdb_target, 100, ["before"], expiry)
        cli(fixture, rdb_target, "SHUTDOWN", "NOSAVE")
        print("OK: Redis RDB native validation + restore preserves data types and absolute expiry; older snapshot lacks later writes")

        aof_target = fixture.engine(IMAGE, "redis")
        fixture.import_tree(aof_target, backup, "/fixture/restore")
        fixture.execute(aof_target, "redis-check-aof", "/fixture/restore/appendonlydir/"+manifests[0].name)
        start(fixture, aof_target, "/fixture/restore", aof=True)
        ready(fixture, aof_target)
        assert_data(fixture, aof_target, 175, ["before", "wanted"], expiry)
        persistence = cli(fixture, aof_target, "INFO", "persistence")
        if "aof_enabled:1" not in persistence or "aof_last_write_status:ok" not in persistence:
            raise RuntimeError("restored target did not retain healthy AOF persistence")
        cli(fixture, aof_target, "SHUTDOWN", "NOSAVE")
        print("OK: Redis complete multipart AOF wins over older RDB, includes wanted writes and excludes later unwanted writes")

        corrupt_rdb = fixture.folder/"bad-rdb"
        shutil.copytree(rdb, corrupt_rdb)
        original = (corrupt_rdb/"dump.rdb").read_bytes()
        (corrupt_rdb/"dump.rdb").write_bytes(original[:-1]+bytes([original[-1] ^ 255]))
        check_rejected(fixture, corrupt_rdb, aof=False,
                       validator=["redis-check-rdb", "/fixture/restore/dump.rdb"], reason="corrupt RDB checksum")
        missing = fixture.folder/"missing-aof"
        shutil.copytree(backup, missing)
        (missing/"appendonlydir"/base_files[0].name).unlink()
        aof_validator = ["redis-check-aof", "/fixture/restore/appendonlydir/"+manifests[0].name]
        check_rejected(fixture, missing, aof=True, validator=aof_validator, reason="manifest with missing AOF base member")
        truncated = fixture.folder/"truncated-aof"
        shutil.copytree(backup, truncated)
        damaged = truncated/"appendonlydir"/incrementals[0].name
        damaged.write_bytes(damaged.read_bytes()[:-3])
        check_rejected(fixture, truncated, aof=True, validator=aof_validator, reason="truncated AOF with truncation disabled")
    print(f"OK: Redis synthetic recovery drill {time.monotonic()-started:.2f}s; no timestamp-PITR, HA or production RPO/RTO claim")


if __name__ == "__main__":
    main()
