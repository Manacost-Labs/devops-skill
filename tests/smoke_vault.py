#!/usr/bin/env python3
"""Actual pinned Vault lifecycle checks on owned in-memory loopback state.

No live endpoint options, stored credentials, skips or simulated Vault API.
Only fixed scenario names, version and numeric metadata reach test output.
"""
from __future__ import annotations

from pathlib import Path
import secrets
import tempfile
import time
import unittest

from vault_fixture import FixtureError, VERSION, VaultLab, verified_binary


class NativeVaultTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = tempfile.TemporaryDirectory(prefix="devops-vault-tools-")
        cls.addClassCleanup(cls.tools.cleanup)
        executable = verified_binary(Path(cls.tools.name))
        cls.lab = VaultLab(executable)
        cls.addClassCleanup(cls.lab.close)
        version = cls.lab.call("GET", "sys/health")["version"]
        if version != VERSION:
            raise FixtureError("native Vault version mismatch")
        cls.lab.call("POST", "sys/policies/acl/reader", {"policy": 'path "secret/data/fixture" { capabilities = ["read"] }'})
        cls.lab.call("POST", "sys/policies/acl/parent", {"policy": 'path "secret/data/fixture" { capabilities = ["read"] }\npath "auth/token/create" { capabilities = ["update"] }'})
        cls.lab.call("POST", "sys/policies/acl/emergency", {"policy": 'path "secret/data/emergency" { capabilities = ["read"] }'})
        cls.lab.call("POST", "secret/data/fixture", {"data": {"value": secrets.token_urlsafe(32)}})
        cls.lab.call("POST", "secret/data/emergency", {"data": {"value": secrets.token_urlsafe(32)}})
        print(f"Verified native Vault {version}; owned loopback dev server; synthetic data only", flush=True)

    def allowed(self, token, path="secret/data/fixture"):
        return self.lab.client.call("GET", path, token)[0] == 200

    def denied(self, token, path="secret/data/fixture"):
        return self.lab.client.call("GET", path, token)[0] == 403

    def revoke(self, auth):
        self.lab.call("POST", "auth/token/revoke-accessor", {"accessor": auth["accessor"]})

    def test_short_grant_positive_and_denied_scope(self):
        auth = self.lab.issue()["auth"]
        self.assertTrue(0 < auth["lease_duration"] <= 30)
        self.assertFalse(auth["renewable"])
        self.assertTrue(self.allowed(auth["client_token"]))
        self.assertTrue(self.denied(auth["client_token"], "secret/data/emergency"))
        metadata = self.lab.call("POST", "auth/token/lookup-accessor", {"accessor": auth["accessor"]})["data"]
        self.assertTrue(metadata["explicit_max_ttl"] == 30 and metadata["expire_time"] is not None)
        self.revoke(auth)
        self.assertTrue(self.denied(auth["client_token"]))

    def test_wrapping_is_single_use_and_separate_from_grant_ttl(self):
        wrapped = self.lab.issue(wrap="10s")
        self.assertTrue(wrapped.get("auth") is None)
        wrapper = wrapped["wrap_info"]["token"]
        first = self.lab.call("POST", "sys/wrapping/unwrap", {}, token=wrapper)
        self.assertTrue(self.allowed(first["auth"]["client_token"]))
        second_status, _ = self.lab.client.call("POST", "sys/wrapping/unwrap", wrapper, {})
        self.assertTrue(second_status in {400, 403})
        self.assertTrue(first["auth"]["lease_duration"] > wrapped["wrap_info"]["ttl"])
        self.revoke(first["auth"])

    def test_partial_consumer_rotation_resume_then_revoke(self):
        old = self.lab.issue()["auth"]
        new = self.lab.issue()["auth"]
        consumers = {"canary": old["client_token"], "worker": old["client_token"]}
        consumers["canary"] = new["client_token"]
        # Inject a consumer delivery failure: worker keeps its observed old
        # reference. Vault authentication is real on both sides of the split.
        self.assertTrue(all(self.allowed(value) for value in consumers.values()))
        self.assertTrue(consumers["worker"] == old["client_token"])
        self.assertTrue(self.allowed(old["client_token"]))
        consumers["worker"] = new["client_token"]
        self.assertTrue(all(value == new["client_token"] and self.allowed(value) for value in consumers.values()))
        self.revoke(old)
        self.assertTrue(self.denied(old["client_token"]))
        self.assertTrue(all(self.allowed(value) for value in consumers.values()))
        self.revoke(new)

    def test_kv_cas_conflict_and_delete_do_not_revoke_copied_data(self):
        first_value, second_value = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        first = self.lab.call("POST", "secret/data/rotation", {"options": {"cas": 0}, "data": {"value": first_value}})["data"]["version"]
        second = self.lab.call("POST", "secret/data/rotation", {"options": {"cas": first}, "data": {"value": second_value}})["data"]["version"]
        conflict, _ = self.lab.client.call("POST", "secret/data/rotation", self.lab.root, {"options": {"cas": first}, "data": {"value": first_value}})
        self.assertEqual(conflict, 400)
        self.assertTrue(self.lab.call("GET", "secret/data/rotation")["data"]["data"]["value"] == second_value)
        copied = self.lab.call("GET", f"secret/data/rotation?version={first}")["data"]["data"]["value"]
        self.lab.call("POST", "secret/delete/rotation", {"versions": [first]})
        self.assertTrue(copied == first_value)
        self.assertEqual(self.lab.client.call("GET", f"secret/data/rotation?version={first}", self.lab.root)[0], 404)
        self.lab.call("POST", "secret/undelete/rotation", {"versions": [first]})
        self.assertTrue(self.lab.call("GET", f"secret/data/rotation?version={first}")["data"]["data"]["value"] == copied)
        self.assertEqual(second, first + 1)

    def test_accessor_revocation_removes_parent_and_derived_child(self):
        parent = self.lab.issue("parent")["auth"]
        child = self.lab.issue("parent", parent=parent["client_token"])["auth"]
        self.assertTrue(self.allowed(parent["client_token"]) and self.allowed(child["client_token"]))
        self.revoke(parent)
        self.assertTrue(self.denied(parent["client_token"]) and self.denied(child["client_token"]))

    def test_revoked_session_can_reauthenticate_until_issuer_is_closed(self):
        self.lab.call("POST", "sys/auth/fixture-userpass", {"type": "userpass"})
        password = secrets.token_urlsafe(32)
        self.lab.call("POST", "auth/fixture-userpass/users/operator", {"password": password, "token_policies": ["reader"], "token_ttl": "30s", "token_max_ttl": "30s"})
        login = {"password": password}
        first = self.lab.call("POST", "auth/fixture-userpass/login/operator", login)["auth"]
        self.revoke(first)
        self.assertTrue(self.denied(first["client_token"]))
        second = self.lab.call("POST", "auth/fixture-userpass/login/operator", login)["auth"]
        self.assertTrue(self.allowed(second["client_token"]))
        self.lab.call("DELETE", "auth/fixture-userpass/users/operator")
        status, _ = self.lab.client.call("POST", "auth/fixture-userpass/login/operator", None, login)
        self.assertTrue(status in {400, 403})
        # Closing the login path does not revoke the already active session.
        self.assertTrue(self.allowed(second["client_token"]))
        self.revoke(second)
        self.assertTrue(self.denied(second["client_token"]))

    def test_emergency_bounded_grant_closeout(self):
        emergency = self.lab.issue("emergency", "10s")["auth"]
        self.assertTrue(self.allowed(emergency["client_token"], "secret/data/emergency"))
        self.assertTrue(self.denied(emergency["client_token"]))
        self.assertTrue(0 < emergency["lease_duration"] <= 10 and not emergency["renewable"])
        self.revoke(emergency)
        self.assertTrue(self.denied(emergency["client_token"], "secret/data/emergency"))
        self.assertTrue(self.allowed(self.lab.root))

    def test_expiry_denies_old_access_and_renewal(self):
        auth = self.lab.issue(ttl="3s")["auth"]
        self.assertTrue(self.allowed(auth["client_token"]))
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline and not self.denied(auth["client_token"]):
            time.sleep(0.2)
        self.assertTrue(self.denied(auth["client_token"]))
        status, _ = self.lab.client.call("POST", "auth/token/renew-self", auth["client_token"], {"increment": "30s"})
        self.assertEqual(status, 403)
        lookup, _ = self.lab.client.call("POST", "auth/token/lookup-accessor", self.lab.root, {"accessor": auth["accessor"]})
        self.assertTrue(lookup in {400, 403})
        self.assertTrue(self.allowed(self.lab.root))


if __name__ == "__main__":
    unittest.main()
