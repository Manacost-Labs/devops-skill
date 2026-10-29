"""Native Linux Docker fixtures; never run on an operating host."""
from __future__ import annotations

import json
import sys

from container_fixture import APP, HTTP, REQUEST, ROOT, DockerFixture, command


def snapshot(fixture, identity):
    raw = fixture.docker("container", "inspect", identity).stdout
    result = command([sys.executable, str(ROOT/"docker-operations/scripts/inspect-container-state.py"), "--id", identity], input=raw)
    return json.loads(result.stdout)


def main():
    fixture = DockerFixture()
    try:
        identity, _ = fixture.execute("block=bytearray(256*1024*1024)", expected=137)
        report = snapshot(fixture, identity)
        assert report["oom_killed"] is True and report["exit_code"] == 137
        # Namespace PID1 has special signal rules: kill from its owning daemon.
        killed = fixture.create("import time; time.sleep(60)")
        fixture.docker("start", killed)
        fixture.owned_container(killed)
        fixture.docker("kill", "--signal", "KILL", killed)
        assert int(fixture.docker("wait", killed).stdout.strip()) == 137
        assert snapshot(fixture, killed)["oom_killed"] is False
        print("OK: actual cgroup OOM distinguished from non-OOM SIGKILL")

        network = fixture.network()
        server = fixture.create(HTTP, ["0.0.0.0"], network=network, alias="fixture-peer")
        fixture.docker("start", server)
        fixture.execute(REQUEST, ["fixture-peer"], network=network)
        local = fixture.create(HTTP, ["127.0.0.1"], network=network, alias="fixture-local")
        fixture.docker("start", local)
        fixture.execute(REQUEST, ["fixture-local"], network=network, expected=23)
        print("OK: peer DNS/request success and DNS-resolved loopback-listener failure")

        data, backup, restored = (fixture.volume(name) for name in ("data", "backup", "restored"))
        mounts = [f"type=volume,source={data},target=/data", f"type=volume,source={backup},target=/backup"]
        for mode in ("init", "backup", "migrate", "write"):
            fixture.execute(APP, [mode], mounts=mounts)
        old, _ = fixture.execute(APP, ["old"], mounts=mounts, expected=20)
        assert snapshot(fixture, old)["exit_code"] == 20
        _, rows = fixture.execute(APP, ["new"], mounts=mounts)
        assert json.loads(rows) == [[1, "before"], [2, "after"]]
        # Restore only to a different volume; current writes remain intact.
        restore_mounts = [f"type=volume,source={backup},target=/backup,readonly",
                          f"type=volume,source={restored},target=/restore"]
        fixture.execute(APP, ["restore"], mounts=restore_mounts)
        _, rows = fixture.execute(APP, ["restored"], mounts=restore_mounts)
        assert json.loads(rows) == [[1, "before"]]
        fixture.execute(APP, ["repair"], mounts=mounts)
        for mode in ("old", "new"):
            _, rows = fixture.execute(APP, [mode], mounts=mounts)
            assert json.loads(rows) == [[1, "before"], [2, "after"]]
        print("OK: old reader rejected after migration; separate old-point restore exposes lost write; forward compatibility repair retains both rows")
    finally:
        fixture.cleanup()
    print("OK: owned Docker containers/network/volumes cleaned; no production target")


if __name__ == "__main__":
    main()
