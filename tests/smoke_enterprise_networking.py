#!/usr/bin/env python3
"""Actual Linux kernel WireGuard/nftables/iproute2 and standalone FRR drills.

Requires a disposable root-owned Linux runner; missing capabilities are failures.
No production interface, route, ruleset or persistent service is modified.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("network_native_audit", ROOT / "enterprise-networking/scripts/snapshot-audit.py")
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)


def run(*argv, input=None, check=True, timeout=12):
    result = subprocess.run(argv, input=input, text=True, capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise RuntimeError(f"fixture command failed: {argv[0]}: {result.stderr[:1500]}")
    return result


def wait_for(check, label, timeout=35):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if check():
            return
        time.sleep(0.5)
    raise AssertionError("convergence timeout: " + label)


def rib_matches(collect, *, present=(), absent=()):
    """One complete collection per observation; unknown is never withdrawal proof."""
    data = collect()
    routes = data.get("routes") if isinstance(data, dict) else None
    return (isinstance(routes, dict) and set(present) <= routes.keys()
            and not set(absent).intersection(routes))


class NetworkFixture:
    def __init__(self):
        if sys.platform != "linux" or os.geteuid() != 0:
            raise RuntimeError("native networking tests require disposable Linux root")
        for binary in ("ip", "wg", "nft", "ping", "sysctl", "vtysh", "/usr/lib/frr/bgpd"):
            if not shutil.which(binary):
                raise RuntimeError("missing mandatory native dependency: " + binary)
        self.folder = Path(tempfile.mkdtemp(prefix="devops-network-"))
        os.chmod(self.folder, 0o700)
        token = uuid.uuid4().hex[:8]
        self.names = {side: "dn-" + token + "-" + side for side in ("a", "b")}
        self.created = []
        self.processes = []
        self.logs = []
        try:
            for side, namespace in self.names.items():
                # Never adopt or delete an existing namespace.
                existing = {line.split()[0] for line in run("ip", "netns", "list").stdout.splitlines()}
                if namespace in existing:
                    raise RuntimeError("fixture namespace collision")
                run("ip", "netns", "add", namespace)
                self.created.append(namespace)
                self.ns(side, "ip", "link", "set", "lo", "up")
                self.ns(side, "sysctl", "-qw", "net.ipv4.conf.all.rp_filter=0", "net.ipv4.conf.default.rp_filter=0")
            for link, subnet in (("u", "192.0.2"), ("r", "198.51.100")):
                left, right = link + token + "a", link + token + "b"
                run("ip", "link", "add", left, "type", "veth", "peer", "name", right)
                try:
                    for side, original, number in (("a", left, 1), ("b", right, 2)):
                        run("ip", "link", "set", original, "netns", self.names[side])
                        self.ns(side, "ip", "link", "set", original, "name", link + "0")
                        self.ns(side, "ip", "addr", "add", f"{subnet}.{number}/30", "dev", link + "0")
                        self.ns(side, "ip", "link", "set", link + "0", "up")
                finally:
                    # If a partial move failed, remove only our randomly named link.
                    run("ip", "link", "del", left, check=False)
                    run("ip", "link", "del", right, check=False)
            keys = {}
            for side, number in (("a", 1), ("b", 2)):
                secret = run("wg", "genkey").stdout
                private = self.folder / (side + ".key")
                private.write_text(secret, encoding="ascii")
                os.chmod(private, 0o600)
                keys[side] = run("wg", "pubkey", input=secret).stdout.strip()
                self.ns(side, "ip", "link", "add", "wg0", "type", "wireguard")
                self.ns(side, "ip", "addr", "add", f"10.99.0.{number}/30", "dev", "wg0")
                self.ns(side, "wg", "set", "wg0", "private-key", str(private), "listen-port", "51820")
                self.ns(side, "ip", "link", "set", "wg0", "mtu", "1380", "up")
                self.ns(side, "ip", "addr", "add", f"10.{10 if side == 'a' else 20}.0.1/32", "dev", "lo")
            for side, peer, number, remote in (("a", "b", 2, "10.20.0.0/24"), ("b", "a", 1, "10.10.0.0/24")):
                self.ns(side, "wg", "set", "wg0", "peer", keys[peer], "endpoint", f"192.0.2.{number}:51820", "allowed-ips", f"10.99.0.{number}/32,{remote}")
                self.ns(side, "ip", "route", "add", remote, "dev", "wg0")
            self.ns("b", "nft", "-f", "-", input='''table inet sentinel {
 chain keep {
  comment "unrelated-owned-sentinel";
 }
}
''')
            self.set_acl("accept")
        except BaseException:
            self.close()
            raise

    def ns(self, side, *argv, **kwargs):
        return run("ip", "netns", "exec", self.names[side], *argv, **kwargs)

    def ping(self, side="a", size=32):
        source, target = ("10.10.0.1", "10.20.0.1") if side == "a" else ("10.20.0.1", "10.10.0.1")
        return self.ns(side, "ping", "-n", "-c", "1", "-W", "1", "-M", "do", "-I", source, "-s", str(size), target, check=False).returncode == 0

    def set_acl(self, verdict):
        if verdict not in {"accept", "drop"}:
            raise ValueError("fixture verdict")
        # Restore only the owned table, in a single atomic nft transaction.
        exists = self.ns("b", "nft", "list", "table", "inet", "fixture", check=False).returncode == 0
        opposite = "drop" if verdict == "accept" else "accept"
        text = ("delete table inet fixture\n" if exists else "") + f'''table inet fixture {{
 chain input {{
  type filter hook input priority 0; policy accept;
  iifname "wg0" ip daddr 10.20.0.1 counter {verdict}
  iifname "wg0" ip daddr 10.20.0.1 counter {opposite}
 }}
}}
'''
        self.ns("b", "nft", "--check", "-f", "-", input=text)
        self.ns("b", "nft", "-f", "-", input=text)

    def start_bgp(self):
        for side, asn, number, peer, remote_as, own, imported in (
                ("a", 65001, 1, 2, 65002, "10.10.0.0/24", "10.20.0.0/24"),
                ("b", 65002, 2, 1, 65001, "10.20.0.0/24", "10.10.0.0/24")):
            directory = self.folder / side
            directory.mkdir(mode=0o700)
            extra = "ip prefix-list EXPORT seq 10 permit 203.0.113.0/24\n" if side == "b" else ""
            network = "  network 203.0.113.0/24\n" if side == "b" else ""
            text = f"""frr defaults traditional
hostname fixture-{side}
log stdout debugging
debug bgp neighbor-events
ip prefix-list IMPORT seq 5 permit {imported}
ip prefix-list EXPORT seq 5 permit {own}
{extra}router bgp {asn}
 bgp router-id 192.0.2.{number}
 bgp ebgp-requires-policy
 no bgp network import-check
 neighbor 10.99.0.{peer} remote-as {remote_as}
 neighbor 10.99.0.{peer} timers 1 3
 address-family ipv4 unicast
  network {own}
{network}  neighbor 10.99.0.{peer} prefix-list IMPORT in
  neighbor 10.99.0.{peer} prefix-list EXPORT out
  neighbor 10.99.0.{peer} soft-reconfiguration inbound
 exit-address-family
"""
            config = directory / "bgpd.conf"
            config.write_text(text, encoding="utf-8")
            self.ns(side, "/usr/lib/frr/bgpd", "-C", "-S", "-Z", "-f", str(config))
            log = (directory / "bgpd.log").open("w", encoding="utf-8")
            self.logs.append(log)
            process = subprocess.Popen(["ip", "netns", "exec", self.names[side], "/usr/lib/frr/bgpd", "-S", "-Z", "-f", str(config), "-i", str(directory / "bgpd.pid"), "--vty_socket", str(directory)], stdout=log, stderr=log)
            self.processes.append(process)
        wait_for(lambda: rib_matches(lambda: self.bgp("a"), present=("10.20.0.0/24",)), "BGP permitted prefix")

    def vty(self, side, *commands):
        argv = ["vtysh", "--vty_socket", str(self.folder / side), "-d", "bgpd"]
        for command in commands:
            argv.extend(("-c", command))
        return self.ns(side, *argv)

    def bgp(self, side):
        try:
            data = json.loads(self.vty(side, "show bgp ipv4 unicast json").stdout)
            if not isinstance(data, dict) or not isinstance(data.get("routes"), dict):
                raise ValueError("incomplete FRR collection")
            return data
        except (RuntimeError, ValueError):
            if any(process.poll() is not None for process in self.processes):
                diagnostics = "\n".join(path.read_text(encoding="utf-8") for path in self.folder.glob("*/bgpd.log"))
                raise RuntimeError("bgpd exited: " + diagnostics[-3000:])
            return None

    def snapshot(self, side="b"):
        return {"routes": json.loads(self.ns(side, "ip", "-j", "-4", "route", "show", "table", "all").stdout),
                "rules": json.loads(self.ns(side, "ip", "-j", "-4", "rule", "show").stdout),
                "nft": json.loads(self.ns(side, "nft", "-j", "list", "ruleset").stdout),
                "bgp": self.bgp(side)}

    def diagnostics(self):
        """Bounded evidence from owned synthetic namespaces only; never read WG keys."""
        for side, peer, local in (("a", "10.99.0.2", "10.99.0.1"), ("b", "10.99.0.1", "10.99.0.2")):
            for command in ("show bgp ipv4 unicast summary json", "show bgp neighbors json", "show bgp ipv4 unicast json", "show ip prefix-list"):
                try:
                    result = self.vty(side, command)
                    print(f"DIAGNOSTIC {side} {command}:\n{result.stdout[:6000]}\n{result.stderr[:1000]}", flush=True)
                except Exception as error:
                    print(f"DIAGNOSTIC {side} {command}: unavailable ({type(error).__name__})", flush=True)
            for command in (("ip", "-j", "addr", "show", "dev", "wg0"),
                            ("ip", "-j", "-4", "route", "get", peer, "from", local),
                            ("ss", "-tnp")):
                try:
                    result = self.ns(side, *command, check=False, timeout=4)
                    print(f"DIAGNOSTIC {side} {command[0]}: exit={result.returncode}\n{result.stdout[:4000]}\n{result.stderr[:1000]}", flush=True)
                except Exception as error:
                    print(f"DIAGNOSTIC {side} {command[0]}: unavailable ({type(error).__name__})", flush=True)
            path = self.folder / side / "bgpd.log"
            try:
                with path.open("rb") as stream:
                    stream.seek(max(0, path.stat().st_size - 8000))
                    tail = stream.read(8000).decode("utf-8", errors="replace")
                print(f"DIAGNOSTIC {side} bgpd log tail:\n{tail}", flush=True)
            except OSError:
                print(f"DIAGNOSTIC {side} bgpd log unavailable", flush=True)

    def close(self):
        for process in getattr(self, "processes", []):
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
        for log in getattr(self, "logs", []): log.close()
        for namespace in reversed(getattr(self, "created", [])):
            run("ip", "netns", "del", namespace, check=False)
        if hasattr(self, "folder"):
            shutil.rmtree(self.folder)


class NativeNetworkingTests(unittest.TestCase):
    def test_actual_tunnel_leak_acl_asymmetry_mtu_and_scoped_recovery(self):
        fixture = NetworkFixture()
        try:
            wait_for(lambda: fixture.ping() and fixture.ping("b"), "bidirectional encrypted data")
            handshake = fixture.ns("a", "wg", "show", "wg0", "latest-handshakes").stdout.split()
            self.assertGreater(int(handshake[1]), 0)
            self.assertTrue(fixture.ping(size=1352))  # 1380 inner MTU minus IPv4/ICMP 28.
            self.assertFalse(fixture.ping(size=1353))
            print("PASS: real encrypted IPv4 MTU boundary (1380); not a PMTUD blackhole test", flush=True)

            fixture.start_bgp()
            self.assertNotIn("203.0.113.0/24", fixture.bgp("a")["routes"])
            before = fixture.snapshot()
            fixture.set_acl("drop")
            self.assertFalse(fixture.ping())
            denied = fixture.snapshot()
            # b deliberately originates the test prefix; it must never be admitted at a.
            b_prefixes = ["10.10.0.0/24", "10.20.0.0/24", "203.0.113.0/24"]
            self.assertEqual(HELPER.audit(before, before, denied, b_prefixes)["status"], "BLOCKED")
            counter = [item["rule"]["expr"][2]["counter"]["packets"] for item in denied["nft"]["nftables"] if "rule" in item and item["rule"]["table"] == "fixture"]
            self.assertGreater(sum(counter), 0)
            fixture.set_acl("accept")
            self.assertTrue(fixture.ping())
            self.assertEqual(HELPER.audit(before, before, fixture.snapshot(), b_prefixes)["status"], "MATCHED")
            self.assertIn("sentinel", fixture.ns("b", "nft", "list", "tables").stdout)
            print("PASS: actual nft first-match accept/drop ordering, denial counters and table-scoped recovery", flush=True)

            fixture.ns("b", "ip", "route", "replace", "10.10.0.0/24", "via", "198.51.100.1", "dev", "r0")
            fixture.ns("b", "sysctl", "-qw", "net.ipv4.conf.all.rp_filter=1", "net.ipv4.conf.wg0.rp_filter=1")
            reverse = json.loads(fixture.ns("b", "ip", "-j", "route", "get", "10.10.0.1", "from", "10.20.0.1").stdout)
            self.assertEqual(reverse[0]["dev"], "r0")
            self.assertFalse(fixture.ping())
            fixture.ns("b", "ip", "route", "replace", "10.10.0.0/24", "dev", "wg0")
            self.assertTrue(fixture.ping())
            print("PASS: asymmetric reverse route with strict rp_filter fails; exact route restore recovers", flush=True)

            # Deliberately admit a forbidden prefix only inside this isolated lab.
            fixture.vty("a", "configure terminal", "ip prefix-list IMPORT seq 10 permit 203.0.113.0/24", "end", "clear bgp 10.99.0.2 soft in")
            wait_for(lambda: rib_matches(lambda: fixture.bgp("a"), present=("203.0.113.0/24",)), "injected prefix leak")
            leaked = fixture.snapshot("a")
            result = HELPER.audit(leaked, leaked, leaked, ["10.10.0.0/24", "10.20.0.0/24"])
            self.assertEqual(result["unexpected_bgp_prefixes"], ["203.0.113.0/24"])
            fixture.vty("a", "configure terminal", "no ip prefix-list IMPORT seq 10", "end", "clear bgp 10.99.0.2 soft in")
            wait_for(lambda: rib_matches(lambda: fixture.bgp("a"), present=("10.20.0.0/24",), absent=("203.0.113.0/24",)), "leak withdrawn, permitted prefix retained")
            print("PASS: actual FRR leak admission, exact-prefix detector and filter rollback withdrawal", flush=True)

            fixture.ns("a", "ip", "link", "set", "wg0", "down")
            self.assertFalse(fixture.ping())
            wait_for(lambda: rib_matches(lambda: fixture.bgp("a"), present=("10.10.0.0/24",), absent=("10.20.0.0/24",)), "tunnel loss BGP withdrawal")
            fixture.ns("a", "ip", "link", "set", "wg0", "up")
            wait_for(lambda: fixture.ping() and fixture.ping("b"), "tunnel data recovery")
            wait_for(lambda: rib_matches(lambda: fixture.bgp("a"), present=("10.20.0.0/24",)), "BGP reconvergence")
            self.assertNotIn("203.0.113.0/24", fixture.bgp("a")["routes"])
            print("PASS: actual tunnel loss, BGP withdrawal and encrypted data/control recovery", flush=True)
        except Exception:
            fixture.diagnostics()
            raise
        finally:
            fixture.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
