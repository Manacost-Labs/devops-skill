from __future__ import annotations
import contextlib, hashlib, importlib.util, io, json, subprocess, sys, tempfile, unittest, warnings, zipfile
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlparse
from unittest import mock
import yaml
ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
NOW = "2026-08-17T10:15:00Z"

def effective_policy(filename):
    policy = json.loads((ROOT / "devops-platform-contracts/policies" / filename).read_text(encoding="utf-8-sig"))
    parent_name = policy.pop("extends", None)
    if parent_name:
        parent = effective_policy(parent_name)
        for key, value in policy.items():
            if isinstance(value, dict) and isinstance(parent.get(key), dict): parent[key].update(value)
            else: parent[key] = value
        policy = parent
    return policy

def policy_binding(filename="default-policy.json"):
    policy = effective_policy(filename)
    canonical = json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return {"id":policy["policy_id"], "version":policy["version"], "digest":"sha256:"+hashlib.sha256(canonical).hexdigest()}

def operation(risk="R2", action="container_rollout", approvals=1, policy_name="default-policy.json"):
    digest = "sha256:" + "1" * 64
    binding = policy_binding(policy_name)
    values = [{"approver":f"user:owner-{index}","role":f"role-{index}","target":"example-lab","plan_digest":digest,"policy_digest":binding["digest"],"approved_at":"2026-08-17T10:00:00Z","expires_at":"2026-08-17T11:00:00Z","evidence_ref":f"ticket:CHG-{index}"} for index in range(approvals)]
    return {
        "schema_version":"2.0","operation_id":"ops-test-000001","objective":"Deploy the approved immutable release","data_classification":"internal",
        "policy":binding,
        "target":{"name":"example-lab","environment":"lab","owner":"team:platform","profile_digest":"sha256:"+"0"*64},
        "change":{"action":action,"risk":risk,"scope":["service:api"],"plan_digest":digest,"stateful":False,"destructive":False,"external_side_effects":risk not in {"R0","R1"}},
        "execution":{"executor":"service:codex","requested_at":"2026-08-17T09:55:00Z","window_start":"2026-08-17T10:00:00Z","window_end":"2026-08-17T11:00:00Z","idempotency_key":"example-000001","change_lock_ref":None},
        "approvals":values,
        "recovery":{"required":False,"method":"previous release","artifact_ref":"release:previous","restore_tested_at":None,"rpo_minutes":None,"rto_minutes":5},
        "verification":{"criteria":["external path returns 2xx"],"observation_window_minutes":10},"exception":None}

class PlatformTests(unittest.TestCase):
    def run(self, *args, **kwargs): return super().run(*args, **kwargs)
    def command(self, *args): return subprocess.run([PYTHON, *map(str, args)], capture_output=True, text=True)
    def test_platform_contracts_validate(self):
        result = self.command(ROOT / "devops-platform-contracts/scripts/validate_platform.py")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
    def test_catalog_is_complete_dependency_closed_and_unambiguous(self):
        catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8-sig"))
        self.assertEqual(catalog["version"], "0.3.0")
        self.assertEqual(len(catalog["skills"]), 20)
        self.assertEqual(set(catalog["profiles"]["all"]), set(catalog["skills"]))
        capability_owners = {}
        for name, metadata in catalog["skills"].items():
            manifest = yaml.safe_load((ROOT / name / "module.yaml").read_text(encoding="utf-8-sig"))
            self.assertEqual(metadata["role"], manifest["kind"])
            for capability in manifest["capabilities"]:
                self.assertNotIn(capability, capability_owners)
                capability_owners[capability] = name
        for profile, names in catalog["profiles"].items():
            self.assertTrue({"devops-platform-contracts", "devops-core"} <= set(names), profile)
            for name in names:
                manifest = yaml.safe_load((ROOT / name / "module.yaml").read_text(encoding="utf-8-sig"))
                dependencies = {item.split()[0] for item in manifest.get("requires", [])}
                self.assertTrue(dependencies <= set(names), f"{profile} omits dependencies for {name}")
    def test_fast_moving_modules_declare_current_official_sources(self):
        expected = {
            "cloudflare-operations": {"developers.cloudflare.com"},
            "iac-operations": {"developer.hashicorp.com", "opentofu.org", "docs.ansible.com", "cloudinit.readthedocs.io"},
            "cicd-operations": {"docs.github.com", "slsa.dev"},
            "data-resilience-operations": {"www.postgresql.org", "redis.io", "csrc.nist.gov"},
            "cloud-aws": {"docs.aws.amazon.com"},
            "cloud-gcp": {"cloud.google.com", "docs.cloud.google.com"},
            "cloud-azure": {"learn.microsoft.com"},
            "cloud-selectel": {"docs.selectel.ru"},
            "kubernetes-operations": {"kubernetes.io"},
        }
        for name, hosts in expected.items():
            manifest = yaml.safe_load((ROOT / name / "module.yaml").read_text(encoding="utf-8-sig"))
            freshness = manifest["source_freshness"]
            self.assertIs(freshness["refresh_before_change"], True)
            age = (date.today() - date.fromisoformat(freshness["last_verified"])).days
            self.assertGreaterEqual(age, 0)
            self.assertLessEqual(age, 183)
            self.assertTrue(all(urlparse(source).scheme == "https" and urlparse(source).hostname in hosts for source in freshness["official_sources"]))
            self.assertEqual(set(freshness["capability_sources"]), set(manifest["capabilities"]))
            self.assertTrue(all(set(sources) <= set(freshness["official_sources"]) for sources in freshness["capability_sources"].values()))
    def test_freshness_validator_fails_closed_at_boundaries(self):
        validator_path = ROOT / "devops-platform-contracts/scripts/validate_platform.py"
        spec = importlib.util.spec_from_file_location("platform_validator", validator_path)
        module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
        source = yaml.safe_load((ROOT / "cloud-aws/module.yaml").read_text(encoding="utf-8-sig"))
        missing = json.loads(json.dumps(source)); missing.pop("source_freshness")
        self.assertIn("must declare", module.validate_freshness("cloud-aws", missing))
        future = json.loads(json.dumps(source)); future["source_freshness"]["last_verified"] = (date.today() + timedelta(days=1)).isoformat()
        self.assertIn("future", module.validate_freshness("cloud-aws", future))
        stale = json.loads(json.dumps(source)); stale["source_freshness"]["last_verified"] = (date.today() - timedelta(days=184)).isoformat()
        self.assertIn("stale", module.validate_freshness("cloud-aws", stale))
        boundary = json.loads(json.dumps(source)); boundary["source_freshness"]["last_verified"] = (date.today() - timedelta(days=183)).isoformat()
        self.assertIsNone(module.validate_freshness("cloud-aws", boundary))
        bad_host = json.loads(json.dumps(source)); bad_host["source_freshness"]["official_sources"][0] = "https://docs.aws.amazon.com.attacker.example/"
        self.assertIn("non-official", module.validate_freshness("cloud-aws", bad_host))
        bad_scheme = json.loads(json.dumps(source)); bad_scheme["source_freshness"]["official_sources"][0] = "http://docs.aws.amazon.com/"
        self.assertIn("non-official", module.validate_freshness("cloud-aws", bad_scheme))
        missing_mapping = json.loads(json.dumps(source)); missing_mapping["source_freshness"]["capability_sources"].pop("aws-account-discovery")
        self.assertIn("map every capability", module.validate_freshness("cloud-aws", missing_mapping))
    def test_runtime_dependency_is_hash_locked(self):
        root_lock = (ROOT / "requirements.txt").read_text(encoding="utf-8").strip()
        embedded_lock = (ROOT / "devops-platform-contracts/requirements.txt").read_text(encoding="utf-8").strip()
        self.assertEqual(root_lock, embedded_lock)
        self.assertTrue(root_lock.startswith("PyYAML==6.0.3 "))
        self.assertEqual(root_lock.count("--hash=sha256:"), 10)
    def test_compose_preflight_rejects_unsafe_workload(self):
        with tempfile.TemporaryDirectory() as directory:
            compose = Path(directory) / "compose.yaml"
            compose.write_text("services:\n  api:\n    image: demo:latest\n    privileged: true\n    environment:\n      API_KEY: literal\n", encoding="utf-8")
            result = self.command(ROOT / "docker-operations/scripts/compose-preflight.py", compose)
            self.assertNotEqual(result.returncode, 0); self.assertIn("literal sensitive", result.stdout)
    def test_installer_is_dry_run_by_default(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.command(ROOT / "tools/install.py", "--destination", directory)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr); self.assertIn("Dry-run only", result.stdout); self.assertEqual(list(Path(directory).iterdir()), [])
    def test_installer_force_preserves_recoverable_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            installer = ROOT / "tools/install.py"
            result = self.command(installer, "--profile", "core", "--destination", directory, "--apply")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            marker = Path(directory)/"devops-core"/"local-owner-file.txt"
            marker.write_text("preserve me", encoding="utf-8")
            result = self.command(installer, "--profile", "core", "--destination", directory, "--apply", "--force")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            backups = list((Path(directory)/".devops-skill-backups").glob("profile-core-*/previous/devops-core"))
            self.assertTrue(backups); self.assertEqual((backups[-1]/marker.name).read_text(encoding="utf-8"), "preserve me")
    def test_installer_rolls_back_every_touched_skill_on_mid_commit_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            installer_path = ROOT / "tools/install.py"
            result = self.command(installer_path, "--profile", "core", "--destination", directory, "--apply")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            destination = Path(directory)
            markers = {}
            for name in ("devops-platform-contracts", "devops-core"):
                marker = destination / name / "owner-marker.txt"
                marker.write_text(f"preserve {name}", encoding="utf-8")
                markers[name] = marker
            spec = importlib.util.spec_from_file_location("transactional_installer", installer_path)
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            real_replace = module.os.replace
            calls = {"count": 0}
            def fail_fourth_replace(source, target):
                calls["count"] += 1
                if calls["count"] == 4: raise OSError("injected mid-profile failure")
                return real_replace(source, target)
            argv = [str(installer_path), "--profile", "core", "--destination", directory, "--apply", "--force"]
            with mock.patch.object(module.os, "replace", side_effect=fail_fourth_replace), mock.patch.object(sys, "argv", argv), contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(module.main(), 1)
            self.assertIn("rollback attempted for every touched skill", output.getvalue())
            for name, marker in markers.items(): self.assertEqual(marker.read_text(encoding="utf-8"), f"preserve {name}")
            failed = list((destination/".devops-skill-backups").glob("profile-core-*/failed/devops-platform-contracts"))
            self.assertTrue(failed)
    def test_installed_core_profile_validates_without_source_tree(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.command(ROOT / "tools/install.py", "--profile", "core", "--destination", directory, "--apply")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = self.command(Path(directory)/"devops-platform-contracts/scripts/validate_platform.py")
            total = len(json.loads((ROOT / "catalog.json").read_text(encoding="utf-8-sig"))["skills"])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr); self.assertIn(f"2/{total}", result.stdout)
    def test_installed_all_profile_is_self_contained(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.command(ROOT / "tools/install.py", "--profile", "all", "--destination", directory, "--apply")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = self.command(Path(directory)/"devops-platform-contracts/scripts/validate_platform.py")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr); self.assertIn("20/20", result.stdout)
    def test_named_provider_profiles_install_and_validate(self):
        for profile in ("aws-platform", "gcp-platform", "azure-platform", "selectel-platform"):
            with self.subTest(profile=profile), tempfile.TemporaryDirectory() as directory:
                result = self.command(ROOT / "tools/install.py", "--profile", profile, "--destination", directory, "--apply")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                result = self.command(Path(directory)/"devops-platform-contracts/scripts/validate_platform.py")
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("compatible installed skills", result.stdout)
    def gate(self, request, directory, policy=None):
        path = Path(directory) / "operation.json"
        path.write_text(json.dumps(request), encoding="utf-8")
        args = [ROOT / "devops-platform-contracts/scripts/operation_gate.py", "--request", path, "--at", NOW]
        if policy: args += ["--policy", policy]
        return self.command(*args)
    def test_gate_allows_bound_r2_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.gate(operation(), directory)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr); self.assertIn("ALLOWED", result.stdout)
    def test_shipped_operation_template_matches_registered_policy(self):
        result = self.command(
            ROOT / "devops-platform-contracts/scripts/operation_gate.py",
            "--request", ROOT / "devops-platform-contracts/templates/operation-request.json",
            "--at", NOW,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(policy_binding()["digest"], result.stdout)
    def test_gate_blocks_v1_boolean_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.gate({"target":"prod-db","environment":"production","action":"database_migration","risk":"R4","stateful":True,"approval":"confirmed","recovery_proof":True}, directory)
            self.assertNotEqual(result.returncode, 0); self.assertIn("schema_version", result.stdout)
    def test_gate_blocks_mismatched_and_expired_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            request = operation()
            request["approvals"][0]["plan_digest"] = "sha256:" + "2" * 64
            request["approvals"][0]["expires_at"] = "2026-08-17T10:05:00Z"
            result = self.gate(request, directory)
            self.assertEqual(result.returncode, 1); self.assertIn("digest does not match", result.stdout); self.assertIn("not currently valid", result.stdout)
    def test_enterprise_gate_requires_two_roles_and_separation(self):
        with tempfile.TemporaryDirectory() as directory:
            request = operation(risk="R3", action="production_deploy", approvals=1, policy_name="enterprise-policy.json")
            request["target"]["environment"] = "production"
            request["execution"]["change_lock_ref"] = "change-lock:prod"
            policy = "enterprise-policy.json"
            result = self.gate(request, directory, policy)
            self.assertEqual(result.returncode, 1); self.assertIn("2 distinct", result.stdout)
            request["approvals"].append({**request["approvals"][0], "approver":"service:codex", "role":"security-owner", "evidence_ref":"ticket:SEC-1"})
            result = self.gate(request, directory, policy)
            self.assertEqual(result.returncode, 1); self.assertIn("executor cannot approve", result.stdout)
    def test_enterprise_gate_allows_two_independent_approvers(self):
        with tempfile.TemporaryDirectory() as directory:
            request = operation(risk="R3", action="production_deploy", approvals=2, policy_name="enterprise-policy.json")
            request["target"]["environment"] = "production"
            request["execution"]["change_lock_ref"] = "change-lock:prod"
            result = self.gate(request, directory, "enterprise-policy.json")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
    def test_gate_binds_registered_policy_and_each_approval(self):
        with tempfile.TemporaryDirectory() as directory:
            request = operation()
            result = self.gate(request, directory, "enterprise-policy.json")
            self.assertEqual(result.returncode, 1)
            self.assertIn("policy.id does not match", result.stdout)
            request = operation(policy_name="enterprise-policy.json")
            request["approvals"][0]["policy_digest"] = "sha256:" + "f" * 64
            result = self.gate(request, directory, "enterprise-policy.json")
            self.assertEqual(result.returncode, 1)
            self.assertIn("policy digest does not match", result.stdout)
    def test_gate_rejects_unregistered_policy_and_malformed_ranges(self):
        with tempfile.TemporaryDirectory() as directory:
            request = operation()
            request["recovery"]["rto_minutes"] = -1
            request["verification"]["observation_window_minutes"] = -1
            result = self.gate(request, directory)
            self.assertEqual(result.returncode, 1)
            self.assertIn("non-negative integer", result.stdout)
            path = Path(directory) / "operation.json"
            path.write_text(json.dumps(operation()), encoding="utf-8")
            result = self.command(ROOT / "devops-platform-contracts/scripts/operation_gate.py", "--request", path, "--at", NOW, "--policy", ROOT / "devops-platform-contracts/policies/default-policy.json")
            self.assertEqual(result.returncode, 2)
            self.assertIn("policy is not registered", result.stdout)
    def test_gate_blocks_unproven_r4_recovery(self):
        with tempfile.TemporaryDirectory() as directory:
            request = operation(risk="R4", action="database_migration", approvals=1)
            request["change"].update({"stateful":True,"destructive":True})
            request["execution"]["change_lock_ref"] = "change-lock:db"
            result = self.gate(request, directory)
            self.assertEqual(result.returncode, 1); self.assertIn("recovery.required", result.stdout); self.assertIn("restore_tested_at", result.stdout)
    def test_gate_blocks_risk_downgrade(self):
        with tempfile.TemporaryDirectory() as directory:
            request = operation(risk="R1", approvals=0)
            request["change"].update({"destructive":True,"external_side_effects":True})
            result = self.gate(request, directory)
            self.assertEqual(result.returncode, 1); self.assertIn("classified R4", result.stdout); self.assertIn("at least R2", result.stdout)
    def test_capability_resolver_finds_docker_module(self):
        result = self.command(ROOT / "devops-platform-contracts/scripts/resolve_capabilities.py", "--capability", "compose-rollout")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr); self.assertIn("docker-operations", result.stdout)
    def test_new_capabilities_resolve_to_exactly_one_owner(self):
        expected = {
            "cloudflare-dns-operations": "cloudflare-operations",
            "terraform-opentofu-plan-apply": "iac-operations",
            "immutable-artifact-promotion": "cicd-operations",
            "isolated-restore-testing": "data-resilience-operations",
            "cloud-provider-identification": "cloud-generic",
            "aws-account-discovery": "cloud-aws",
            "gcp-project-discovery": "cloud-gcp",
            "azure-subscription-discovery": "cloud-azure",
            "selectel-project-discovery": "cloud-selectel",
            "kubernetes-server-side-apply": "kubernetes-operations",
            "bgp-operations": "enterprise-networking",
            "credential-rotation": "secrets-access-operations",
            "control-evidence-mapping": "security-compliance-operations",
        }
        resolver = ROOT / "devops-platform-contracts/scripts/resolve_capabilities.py"
        for capability, owner in expected.items():
            result = self.command(resolver, "--capability", capability)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            candidates = json.loads(result.stdout)["candidates"]
            self.assertEqual([candidate["module"] for candidate in candidates], [owner])
    def test_resolver_requires_complete_union_coverage(self):
        resolver = ROOT / "devops-platform-contracts/scripts/resolve_capabilities.py"
        result = self.command(resolver, "--capability", "aws-account-discovery", "--capability", "kubernetes-cluster-workload-audit")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["unresolved"], [])
        self.assertEqual(payload["selected"], ["cloud-aws", "kubernetes-operations"])
        result = self.command(resolver, "--capability", "aws-account-discovery", "--capability", "capability-that-does-not-exist")
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["covered"], ["aws-account-discovery"])
        self.assertEqual(payload["unresolved"], ["capability-that-does-not-exist"])
    def test_target_profile_digest_is_canonical(self):
        with tempfile.TemporaryDirectory() as directory:
            profile = Path(directory)/"target-profile.yaml"
            profile.write_text("schema_version: '2.0'\nname: lab\nenvironment: lab\nowner: team\ndata_classification: internal\nservices: []\naccess:\n  ssh: ssh-config:lab\nrisk_overrides:\n  production_confirmation: required\n  destructive_confirmation: required\n", encoding="utf-8")
            tool = ROOT / "devops-core/scripts/profile_digest.py"
            first = self.command(tool, profile)
            self.assertEqual(first.returncode, 0, first.stdout + first.stderr)
            profile.write_text("# reordered with comment\nowner: team\nname: lab\nschema_version: '2.0'\nenvironment: lab\ndata_classification: internal\naccess: {ssh: 'ssh-config:lab'}\nservices: []\nrisk_overrides: {destructive_confirmation: required, production_confirmation: required}\n", encoding="utf-8")
            second = self.command(tool, profile)
            self.assertEqual(first.stdout, second.stdout)
    def test_ledger_chain_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger, record = Path(directory)/"ledger.jsonl", Path(directory)/"record.json"
            record.write_text(json.dumps({"schema_version":"2.0","operation_id":"ops-ledger-0001","policy_id":"default-baseline","target":"lab","target_profile_digest":"sha256:"+"0"*64,"environment":"lab","risk":"R1","plan_digest":"sha256:"+"1"*64,"modules":["devops-core"],"actor":"service:codex","approval_refs":[],"changes":[],"verification":["store:item-1"],"rollback":{"result":"not-required"},"status":"verified","started_at":"2026-08-17T10:00:00Z","finished_at":"2026-08-17T10:01:00Z"}), encoding="utf-8")
            tool = ROOT / "devops-platform-contracts/scripts/ledger_chain.py"
            result = self.command(tool, "append", ledger, record)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(self.command(tool, "verify", ledger).returncode, 0)
            ledger.write_text(ledger.read_text(encoding="utf-8").replace("verified", "blocked"), encoding="utf-8")
            self.assertNotEqual(self.command(tool, "verify", ledger).returncode, 0)
    def test_release_is_deterministic_allowlisted_and_verifiable(self):
        with tempfile.TemporaryDirectory() as directory:
            first, second = Path(directory)/"one.zip", Path(directory)/"two.zip"
            builder = ROOT / "tools/build_release.py"
            for output in (first, second):
                result = self.command(builder, "--output", output)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(first.read_bytes(), second.read_bytes())
            result = self.command(ROOT / "tools/verify_release.py", first)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            with zipfile.ZipFile(first) as archive:
                names = set(archive.namelist())
                self.assertTrue(all(info.create_system == 3 for info in archive.infolist()))
                self.assertTrue({"LICENSE", "README.md", "SECURITY.md", "GOVERNANCE.md", "SUPPORT.md", "CONTRIBUTING.md", "CHANGELOG.md", "tools/install.py", "tools/verify_release.py"} <= names)
                self.assertFalse(any(name.startswith(("lab-artifacts/", "operations/", ".github/")) for name in names))
                manifest = json.loads(archive.read("RELEASE-MANIFEST.json"))
                self.assertEqual(manifest["license"], "Apache-2.0")
                self.assertEqual(manifest["version"], "0.3.0")
                self.assertEqual([item["path"] for item in manifest["files"]], sorted(item["path"] for item in manifest["files"]))
                unpacked = Path(directory) / "unpacked"
                archive.extractall(unpacked)
            installed = Path(directory) / "installed"
            result = self.command(unpacked / "tools/install.py", "--profile", "core", "--destination", installed, "--apply")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            result = self.command(installed / "devops-platform-contracts/scripts/validate_platform.py")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = bytearray(first.read_bytes()); payload[-20] ^= 1; first.write_bytes(payload)
            self.assertNotEqual(self.command(ROOT / "tools/verify_release.py", first).returncode, 0)
    def test_release_verifier_rejects_archive_path_attacks(self):
        with tempfile.TemporaryDirectory() as directory:
            verifier = ROOT / "tools/verify_release.py"
            cases = {
                "traversal.zip": [("../escape", 0o100644)],
                "symlink.zip": [("bad-link", 0o120777)],
                "collision.zip": [("README.md", 0o100644), ("readme.md", 0o100644)],
                "duplicate.zip": [("LICENSE", 0o100644), ("LICENSE", 0o100644)],
            }
            for filename, entries in cases.items():
                with self.subTest(filename=filename):
                    path = Path(directory) / filename
                    with warnings.catch_warnings(), zipfile.ZipFile(path, "w") as archive:
                        warnings.simplefilter("ignore", UserWarning)
                        for name, mode in entries:
                            info = zipfile.ZipInfo(name); info.external_attr = mode << 16
                            archive.writestr(info, b"x")
                    self.assertNotEqual(self.command(verifier, path).returncode, 0)
    def test_public_source_export_is_allowlisted_and_history_free(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "public-source"
            result = self.command(ROOT / "tools/build_public_source.py", "--output", output)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            paths = {path.relative_to(output).as_posix() for path in output.rglob("*") if path.is_file()}
            self.assertIn("PUBLIC-SOURCE-MANIFEST.json", paths)
            self.assertTrue({".github/workflows/validate.yml", "tests/test_platform.py", "tools/build_release.py"} <= paths)
            self.assertFalse(any(path.startswith(("operations/", "lab-artifacts/", ".git/", "dist/")) for path in paths))
            manifest = json.loads((output / "PUBLIC-SOURCE-MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual([item["path"] for item in manifest["files"]], sorted(item["path"] for item in manifest["files"]))
            declared = {item["path"]: item for item in manifest["files"]}
            self.assertEqual(set(declared), paths - {"PUBLIC-SOURCE-MANIFEST.json"})
            for relative, item in declared.items():
                data = (output / relative).read_bytes()
                self.assertNotIn(b"\r", data)
                self.assertEqual(item["sha256"], "sha256:" + hashlib.sha256(data).hexdigest())
                self.assertEqual(item["size"], len(data))
            blocked = self.command(ROOT / "tools/build_public_source.py", "--output", output)
            self.assertNotEqual(blocked.returncode, 0)
    def test_evaluation_suite_covers_new_trust_boundaries(self):
        scenarios = json.loads((ROOT / "evaluations/scenarios.json").read_text(encoding="utf-8-sig"))
        ids = [scenario["id"] for scenario in scenarios]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertGreaterEqual(len(scenarios), 25)
        for scenario in scenarios:
            self.assertEqual(set(scenario), {"id", "request", "fixture", "expected"})
            self.assertTrue(all(isinstance(scenario[field], str) and scenario[field].strip() for field in ("id", "request", "fixture")))
            self.assertIsInstance(scenario["expected"], list); self.assertGreaterEqual(len(scenario["expected"]), 2)
            self.assertTrue(all(isinstance(item, str) and item.strip() for item in scenario["expected"]))
        self.assertTrue({
            "terraform-saved-plan-substitution", "cicd-untrusted-production-runner", "cloudflare-origin-exposure",
            "postgres-restore-data-egress", "cloud-cross-tenant", "provider-source-stale", "kubernetes-context-drift",
            "bgp-prefix-leak", "literal-secret-request", "compliance-certification-overclaim"
        } <= set(ids))
    def test_http_tools_block_loopback_without_override(self):
        result = self.command(ROOT / "network-edge-operations/scripts/http-path-check.py", "http://127.0.0.1/")
        self.assertEqual(result.returncode, 1); self.assertIn("private/special destination blocked", result.stdout)
if __name__ == "__main__": unittest.main()
