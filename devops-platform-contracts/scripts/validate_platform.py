#!/usr/bin/env python3
"""Validate catalog, manifests, shared policy, and cross-module dependencies."""
from __future__ import annotations
import json, re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse
import yaml
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
ROOT = PACKAGE_ROOT.parent
SOURCE_LAYOUT = (ROOT / "catalog.json").is_file()
CATALOG_PATH = ROOT / "catalog.json" if SOURCE_LAYOUT else PACKAGE_ROOT / "catalog.json"
SECRET_KEYS = {"token", "password", "secret", "private_key", "private-key", "api_key", "api-key"}
REQUIRED = {"name": str, "version": str, "kind": str, "capabilities": list, "allowed_tools": list}
SEMVER = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")
REQ = re.compile(r"^([a-z0-9-]+)(?:\s*(>=|==)\s*(\d+\.\d+\.\d+))?$")
NAME = re.compile(r"^[a-z0-9-]{1,63}$")
TOKEN = re.compile(r"^[a-z0-9-]+$")
TOOL = re.compile(r"^[A-Z][A-Za-z]*(\([^(),]+\))?$")
POLICY_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,79}$")
LOCKED_REQUIREMENT = re.compile(r"^[A-Za-z0-9_.-]+==[^\s]+(?:\s+--hash=sha256:[0-9a-f]{64})+$")
FRONTMATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
RESOURCE_LINK = re.compile(r"`((?:references|scripts|templates)/[^`\s]+)`")
MANIFEST_KEYS = {"name", "version", "kind", "requires", "capabilities", "allowed_tools", "risk_domains", "platforms", "provides", "source_freshness"}
CATALOG_KEYS = {"name", "version", "contract_version", "skills", "profiles"}
SKILL_META_KEYS = {"version", "role"}
KINDS = {"coordinator", "executor", "policy-and-validation"}
POLICY_KEYS = {"version", "policy_id", "risk_classes", "approval_ttl_minutes", "minimum_approvals", "require_separation_of_duties", "require_change_lock", "require_plan_digest", "always_require_approval", "require_recovery_evidence", "deny_by_default", "completion_statuses", "exceptions", "ledger", "data"}
POLICY_LIST_FIELDS = ("require_change_lock", "require_plan_digest", "always_require_approval", "require_recovery_evidence", "deny_by_default")
FRESHNESS_HOSTS = {
    "cloudflare-operations": {"developers.cloudflare.com"},
    "iac-operations": {"developer.hashicorp.com", "opentofu.org", "docs.ansible.com", "cloudinit.readthedocs.io"},
    "cicd-operations": {"docs.github.com", "slsa.dev"},
    "github-operations": {"docs.github.com"},
    "data-resilience-operations": {"www.postgresql.org", "redis.io", "csrc.nist.gov"},
    "cloud-aws": {"docs.aws.amazon.com"},
    "cloud-gcp": {"cloud.google.com", "docs.cloud.google.com"},
    "cloud-azure": {"learn.microsoft.com"},
    "cloud-selectel": {"docs.selectel.ru"},
    "kubernetes-operations": {"kubernetes.io"},
}
def parse_version(value):
    found = SEMVER.match(value)
    return tuple(map(int, found.groups())) if found else None
def secret_path(value, path=""):
    if isinstance(value, dict):
        for key, item in value.items():
            p = f"{path}.{key}" if path else str(key)
            if str(key).lower() in SECRET_KEYS: return p
            result = secret_path(item, p)
            if result: return result
    if isinstance(value, list):
        for i, item in enumerate(value):
            result = secret_path(item, f"{path}[{i}]")
            if result: return result
    return None
def fail(message): print(f"ERROR: {message}"); return 1
def validate_freshness(name, data):
    freshness = data.get("source_freshness")
    if freshness is None:
        return f"{name} must declare source_freshness" if name in FRESHNESS_HOSTS else None
    required = {"last_verified", "refresh_before_change", "official_sources", "capability_sources"}
    if not isinstance(freshness, dict) or set(freshness) != required:
        return f"{name} must declare exact source_freshness fields"
    if freshness.get("refresh_before_change") is not True:
        return f"{name} must refresh official sources before change"
    try: verified = date.fromisoformat(freshness.get("last_verified", ""))
    except (TypeError, ValueError): return f"{name} last_verified must be an ISO date"
    age = (date.today() - verified).days
    if age < 0: return f"{name} last_verified cannot be in the future"
    if age > 183: return f"{name} provider sources are stale ({age} days)"
    sources = freshness.get("official_sources")
    if not isinstance(sources, list) or not sources: return f"{name} must list official sources"
    allowed = FRESHNESS_HOSTS.get(name)
    for source in sources:
        parsed = urlparse(source) if isinstance(source, str) else None
        if not parsed or parsed.scheme != "https" or not parsed.hostname or (allowed and parsed.hostname not in allowed):
            return f"{name} has non-official or invalid source: {source}"
    capability_sources = freshness.get("capability_sources")
    if not isinstance(capability_sources, dict) or set(capability_sources) != set(data.get("capabilities", [])):
        return f"{name} must map every capability to official sources"
    for capability, mapped_sources in capability_sources.items():
        if not isinstance(mapped_sources, list) or not mapped_sources or len(mapped_sources) != len(set(mapped_sources)):
            return f"{name} capability source mapping is invalid for {capability}"
        if any(source not in sources for source in mapped_sources):
            return f"{name} capability {capability} references an undeclared official source"
    return None
def validate_skill(name, folder, allowed_tools):
    skill_path = folder / "SKILL.md"
    text = skill_path.read_text(encoding="utf-8-sig")
    if "\r" in text: return f"{name} SKILL.md contains stray CR characters"
    match = FRONTMATTER.match(text)
    if not match: return f"{name} SKILL.md has invalid frontmatter"
    metadata = yaml.safe_load(match.group(1))
    if not isinstance(metadata, dict) or set(metadata) != {"name", "description", "allowed-tools"}: return f"{name} SKILL.md frontmatter must contain only name, description, and allowed-tools"
    if metadata.get("name") != name or not isinstance(metadata.get("description"), str): return f"{name} SKILL.md metadata mismatch"
    declared = metadata.get("allowed-tools")
    if not isinstance(declared, str) or not declared.strip(): return f"{name} SKILL.md must declare a non-empty allowed-tools list"
    if [item.strip() for item in declared.split(",")] != allowed_tools: return f"{name} SKILL.md allowed-tools must match the manifest allowed_tools exactly"
    if len(text.splitlines()) > 500: return f"{name} SKILL.md exceeds 500 lines"
    for relative in RESOURCE_LINK.findall(text):
        clean = relative.rstrip(".,;:)")
        if not (folder / clean).is_file(): return f"{name} references missing resource {clean}"
    agent_path = folder / "agents" / "openai.yaml"
    if not agent_path.is_file(): return f"{name} is missing agents/openai.yaml"
    agent = yaml.safe_load(agent_path.read_text(encoding="utf-8-sig"))
    interface = agent.get("interface", {}) if isinstance(agent, dict) else {}
    short = interface.get("short_description", "")
    prompt = interface.get("default_prompt", "")
    if not 25 <= len(short) <= 64: return f"{name} short_description must be 25-64 characters"
    if f"${name}" not in prompt: return f"{name} default_prompt must mention ${name}"
    return None
def merge_policy(base, override):
    result = dict(base)
    for key, value in override.items():
        if key == "extends": continue
        if isinstance(value, dict) and isinstance(result.get(key), dict): result[key] = merge_policy(result[key], value)
        else: result[key] = value
    return result
def validate_policy(policy, label):
    risks = ["R0", "R1", "R2", "R3", "R4"]
    if not isinstance(policy, dict) or set(policy) != POLICY_KEYS: return f"{label} fields are invalid"
    if policy.get("version") != "2.0" or policy.get("risk_classes") != risks: return f"{label} must define contract 2.0 risk classes in order"
    if not isinstance(policy.get("policy_id"), str) or not POLICY_ID.fullmatch(policy["policy_id"]): return f"{label} policy_id is invalid"
    if type(policy.get("approval_ttl_minutes")) is not int or policy["approval_ttl_minutes"] <= 0: return f"{label} approval_ttl_minutes must be positive"
    for field in ("minimum_approvals", "require_separation_of_duties"):
        values = policy.get(field)
        if not isinstance(values, dict) or set(values) != set(risks): return f"{label} {field} must cover all risk classes"
    if any(type(value) is not int or value < 0 for value in policy["minimum_approvals"].values()): return f"{label} minimum approvals are invalid"
    if any(type(value) is not bool for value in policy["require_separation_of_duties"].values()): return f"{label} separation-of-duties values are invalid"
    for field in POLICY_LIST_FIELDS:
        values = policy.get(field)
        if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values) or len(values) != len(set(values)): return f"{label} {field} is invalid"
    if not set(policy["require_change_lock"]) <= set(risks) or not set(policy["require_plan_digest"]) <= set(risks): return f"{label} risk controls are invalid"
    statuses = policy.get("completion_statuses")
    if not isinstance(statuses, list) or set(statuses) != {"verified", "partially_verified", "rolled_back", "blocked"}: return f"{label} completion statuses are invalid"
    exceptions = policy.get("exceptions")
    if not isinstance(exceptions, dict) or set(exceptions) != {"allowed", "max_ttl_minutes", "minimum_compensating_controls", "never_waive"}: return f"{label} exceptions are invalid"
    if type(exceptions["allowed"]) is not bool or type(exceptions["max_ttl_minutes"]) is not int or exceptions["max_ttl_minutes"] <= 0: return f"{label} exception policy is invalid"
    if type(exceptions["minimum_compensating_controls"]) is not int or exceptions["minimum_compensating_controls"] < 1: return f"{label} compensating controls are invalid"
    if not isinstance(exceptions["never_waive"], list) or not exceptions["never_waive"] or any(not isinstance(value, str) or not value for value in exceptions["never_waive"]) or len(exceptions["never_waive"]) != len(set(exceptions["never_waive"])): return f"{label} never_waive is invalid"
    ledger = policy.get("ledger")
    if not isinstance(ledger, dict) or set(ledger) != {"hash_chain", "external_immutable_sink_required"} or any(type(value) is not bool for value in ledger.values()): return f"{label} ledger controls are invalid"
    data = policy.get("data")
    if not isinstance(data, dict) or set(data) != {"allowed_classifications", "default"}: return f"{label} data policy is invalid"
    allowed = data["allowed_classifications"]
    if not isinstance(allowed, list) or not allowed or any(not isinstance(value, str) for value in allowed) or len(allowed) != len(set(allowed)) or not set(allowed) <= {"public", "internal", "confidential", "restricted"}: return f"{label} data classifications are invalid"
    if data["default"] not in allowed: return f"{label} default data classification is invalid"
    return None
def main() -> int:
    try:
        catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8-sig"))
        policy = json.loads((ROOT / "devops-platform-contracts/policies/default-policy.json").read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as err: return fail(f"platform metadata invalid: {err}")
    if not isinstance(catalog, dict) or set(catalog) != CATALOG_KEYS: return fail("catalog fields are invalid")
    if catalog.get("name") != "devops-skill-platform" or parse_version(catalog.get("version", "")) is None: return fail("catalog name/version is invalid")
    skills = catalog.get("skills", {})
    if not isinstance(skills, dict) or not skills: return fail("catalog has no skills")
    if catalog.get("contract_version") != "v2": return fail("catalog contract_version must be v2")
    embedded_catalog = PACKAGE_ROOT / "catalog.json"
    if not embedded_catalog.is_file(): return fail("installed runtime catalog is missing")
    if json.loads(embedded_catalog.read_text(encoding="utf-8-sig")) != catalog: return fail("root and embedded runtime catalogs differ")
    requirements_path = ROOT / "requirements.txt" if (ROOT / "requirements.txt").is_file() else PACKAGE_ROOT / "requirements.txt"
    requirements = [line.strip() for line in requirements_path.read_text(encoding="utf-8").splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if not requirements or any(not LOCKED_REQUIREMENT.fullmatch(line) for line in requirements): return fail("runtime dependencies must be exactly pinned and SHA-256 locked")
    embedded_requirements = PACKAGE_ROOT / "requirements.txt"
    if not embedded_requirements.is_file(): return fail("installed runtime requirements are missing")
    if (ROOT / "requirements.txt").is_file() and embedded_requirements.read_text(encoding="utf-8") != (ROOT / "requirements.txt").read_text(encoding="utf-8"): return fail("root and embedded runtime requirements differ")
    manifests = {}
    for name, meta in skills.items():
        if not NAME.fullmatch(name) or not isinstance(meta, dict) or set(meta) != SKILL_META_KEYS:
            return fail(f"catalog metadata is invalid for {name}")
        if parse_version(meta.get("version", "")) is None or meta.get("role") not in KINDS:
            return fail(f"catalog role/version is invalid for {name}")
        folder, manifest_path = ROOT / name, ROOT / name / "module.yaml"
        if not (folder / "SKILL.md").is_file() or not manifest_path.is_file():
            if SOURCE_LAYOUT: return fail(f"{name} is missing SKILL.md or module.yaml")
            continue
        try: data = yaml.safe_load(manifest_path.read_text(encoding="utf-8-sig"))
        except yaml.YAMLError as err: return fail(f"{name} manifest YAML invalid: {err}")
        if not isinstance(data, dict): return fail(f"{name} manifest is not a mapping")
        if set(data) - MANIFEST_KEYS: return fail(f"{name} manifest contains unknown fields: {sorted(set(data) - MANIFEST_KEYS)}")
        if secret_path(data): return fail(f"{name} manifest contains literal secret field: {secret_path(data)}")
        for key, expected in REQUIRED.items():
            if not isinstance(data.get(key), expected): return fail(f"{name} manifest field {key} must be {expected.__name__}")
        version = parse_version(data["version"])
        if data["name"] != name or not NAME.fullmatch(data["name"]) or version is None: return fail(f"invalid name/version for {name}")
        if data["kind"] not in KINDS or data["kind"] != meta["role"]: return fail(f"catalog/module role mismatch for {name}")
        if data["version"] != meta.get("version"): return fail(f"catalog/module version mismatch for {name}")
        tools = data["allowed_tools"]
        if not tools or any(not isinstance(value, str) or not TOOL.fullmatch(value) for value in tools): return fail(f"{name} allowed_tools must be non-empty valid tool declarations")
        if len(tools) != len(set(tools)): return fail(f"{name} allowed_tools contains duplicates")
        skill_error = validate_skill(name, folder, tools)
        if skill_error: return fail(skill_error)
        freshness_error = validate_freshness(name, data)
        if freshness_error: return fail(freshness_error)
        for field in ("capabilities", "risk_domains", "platforms", "provides"):
            values = data.get(field, [])
            if not isinstance(values, list) or any(not isinstance(value, str) or not value for value in values): return fail(f"{name} manifest field {field} must contain strings")
            if len(values) != len(set(values)): return fail(f"{name} manifest field {field} contains duplicates")
        if not data["capabilities"] or any(not TOKEN.fullmatch(value) for value in data["capabilities"]): return fail(f"{name} capabilities are invalid")
        if any(not TOKEN.fullmatch(value) for value in data.get("risk_domains", [])): return fail(f"{name} risk domains are invalid")
        requires = data.get("requires", [])
        if not isinstance(requires, list) or any(not isinstance(value, str) for value in requires) or len(requires) != len(set(requires)):
            return fail(f"{name} dependencies are invalid")
        manifests[name] = data
    capability_owners = {}
    for name, data in manifests.items():
        for capability in data["capabilities"]:
            if capability in capability_owners: return fail(f"capability {capability} is owned by both {capability_owners[capability]} and {name}")
            capability_owners[capability] = name
    for name, data in manifests.items():
        for raw in data.get("requires", []):
            match = REQ.match(str(raw))
            if not match: return fail(f"{name} has invalid dependency expression: {raw}")
            dependency, operator, requested = match.groups()
            if dependency not in manifests: return fail(f"{name} requires unknown skill {dependency}")
            installed = parse_version(manifests[dependency]["version"])
            if operator == ">=" and installed < parse_version(requested): return fail(f"{name} requires {raw}, installed {manifests[dependency]['version']}")
            if operator == "==" and installed != parse_version(requested): return fail(f"{name} requires {raw}, installed {manifests[dependency]['version']}")
    profiles = catalog.get("profiles", {})
    if not isinstance(profiles, dict) or not profiles: return fail("catalog has no install profiles")
    for profile, names in profiles.items():
        if not isinstance(names, list) or not names or any(not isinstance(name, str) for name in names):
            return fail(f"profile {profile} must be a non-empty skill list")
        if len(names) != len(set(names)): return fail(f"profile {profile} contains duplicate skills")
        if set(names) - set(skills): return fail(f"profile {profile} references unknown skill")
        if not {"devops-platform-contracts", "devops-core"} <= set(names):
            return fail(f"profile {profile} must include platform contracts and core")
        for name in names:
            for raw in manifests.get(name, {}).get("requires", []):
                dependency = REQ.match(str(raw)).group(1)
                if dependency not in names: return fail(f"profile {profile} omits dependency {dependency} required by {name}")
    if set(profiles.get("all", [])) != set(skills): return fail("profile all must contain every catalog skill")
    policy_error = validate_policy(policy, "default policy")
    if policy_error: return fail(policy_error)
    try:
        enterprise = json.loads((ROOT / "devops-platform-contracts/policies/enterprise-policy.json").read_text(encoding="utf-8-sig"))
        for schema in (ROOT / "devops-platform-contracts/schemas").glob("*.json"):
            parsed = json.loads(schema.read_text(encoding="utf-8-sig"))
            if parsed.get("$schema") != "https://json-schema.org/draft/2020-12/schema": return fail(f"{schema.name} is not JSON Schema 2020-12")
    except (OSError, json.JSONDecodeError) as err: return fail(f"enterprise policy or schema invalid: {err}")
    if enterprise.get("extends") != "default-policy.json": return fail("enterprise policy must extend default-policy.json")
    merged_enterprise = merge_policy(policy, enterprise)
    policy_error = validate_policy(merged_enterprise, "enterprise policy")
    if policy_error: return fail(policy_error)
    if merged_enterprise["approval_ttl_minutes"] > policy["approval_ttl_minutes"]: return fail("enterprise policy cannot lengthen approval TTL")
    if any(merged_enterprise["minimum_approvals"][risk] < policy["minimum_approvals"][risk] for risk in policy["risk_classes"]): return fail("enterprise policy cannot reduce approval counts")
    if any(policy["require_separation_of_duties"][risk] and not merged_enterprise["require_separation_of_duties"][risk] for risk in policy["risk_classes"]): return fail("enterprise policy cannot weaken separation of duties")
    for field in POLICY_LIST_FIELDS:
        if not set(merged_enterprise.get(field, [])) >= set(policy.get(field, [])): return fail(f"enterprise policy weakens {field}")
    parent_exceptions, child_exceptions = policy["exceptions"], merged_enterprise["exceptions"]
    if (not parent_exceptions["allowed"] and child_exceptions["allowed"]) or child_exceptions["max_ttl_minutes"] > parent_exceptions["max_ttl_minutes"]: return fail("enterprise policy weakens exception availability or TTL")
    if child_exceptions["minimum_compensating_controls"] < parent_exceptions["minimum_compensating_controls"] or not set(child_exceptions["never_waive"]) >= set(parent_exceptions["never_waive"]): return fail("enterprise policy weakens exception controls")
    if any(policy["ledger"][field] and not merged_enterprise["ledger"][field] for field in policy["ledger"]): return fail("enterprise policy weakens ledger controls")
    if not set(merged_enterprise["data"]["allowed_classifications"]) <= set(policy["data"]["allowed_classifications"]): return fail("enterprise policy broadens data classifications")
    print(f"OK: platform {catalog['name']} {catalog['version']} with {len(manifests)}/{len(skills)} compatible installed skills.")
    return 0
if __name__ == "__main__": raise SystemExit(main())
