#!/usr/bin/env python3
"""Verify an allowlisted DevOps skill release archive before extraction."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
import zipfile
from pathlib import PurePosixPath, Path

DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
MANIFEST_KEYS = {"schema_version", "name", "version", "contract_version", "license", "files", "excluded_source_classes"}
FILE_KEYS = {"path", "sha256", "size"}
REQUIRED_ROOT_FILES = {"catalog.json", "requirements.txt", "README.md", "SECURITY.md", "LICENSE", "CONTRIBUTING.md", "GOVERNANCE.md", "SUPPORT.md", "CHANGELOG.md"}
REQUIRED_TOOL_FILES = {"tools/install.py", "tools/verify_release.py"}
ALLOWED_SKILL_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".py", ".ps1", ".txt"}
SPECIAL_SKILL_FILES = {"host-audit"}
CATALOG_KEYS = {"name", "version", "contract_version", "skills", "profiles"}
WINDOWS_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}
EXPECTED_EXCLUDED = [".git", "lab-artifacts", "operations", "tests", "target-specific-tools", "development-only-tools", "caches", "credentials"]


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def safe_name(name: str) -> bool:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or "\\" in name or name.startswith("/") or len(name) > 240:
        return False
    for part in path.parts:
        if part in {"", ".", ".."} or part.rstrip(" .") != part:
            return False
        if any(ord(character) < 32 or character in '<>:"|?*' for character in part):
            return False
        if part.split(".", 1)[0].upper() in WINDOWS_RESERVED:
            return False
    return True


def allowed_release_path(name: str, skills: set[str]) -> bool:
    parts = PurePosixPath(name).parts
    if len(parts) == 1:
        return name in REQUIRED_ROOT_FILES
    if parts[0] == "tools":
        return name in REQUIRED_TOOL_FILES
    if parts[0] == "docs":
        return PurePosixPath(name).suffix.lower() == ".md"
    if parts[0] not in skills:
        return False
    path = PurePosixPath(name)
    return path.suffix.lower() in ALLOWED_SKILL_SUFFIXES or path.name in SPECIAL_SKILL_FILES


def parse_catalog(data: bytes) -> dict:
    catalog = json.loads(data.decode("utf-8-sig"))
    if not isinstance(catalog, dict) or set(catalog) != CATALOG_KEYS:
        raise ValueError("catalog fields are invalid")
    if catalog.get("contract_version") != "v2" or not all(isinstance(catalog.get(key), str) and catalog[key] for key in ("name", "version")):
        raise ValueError("catalog identity is invalid")
    skills = catalog.get("skills")
    if not isinstance(skills, dict) or not skills:
        raise ValueError("catalog skills are invalid")
    for name, metadata in skills.items():
        if not isinstance(name, str) or not safe_name(name) or "/" in name:
            raise ValueError("catalog contains an unsafe skill name")
        if not isinstance(metadata, dict) or set(metadata) != {"version", "role"}:
            raise ValueError(f"catalog metadata is invalid for {name}")
        if not isinstance(metadata.get("version"), str) or metadata.get("role") not in {"coordinator", "executor", "policy-and-validation"}:
            raise ValueError(f"catalog version or role is invalid for {name}")
    profiles = catalog.get("profiles")
    if not isinstance(profiles, dict) or not profiles:
        raise ValueError("catalog profiles are invalid")
    for profile, names in profiles.items():
        if not isinstance(profile, str) or not isinstance(names, list) or not names or len(names) != len(set(names)) or any(name not in skills for name in names):
            raise ValueError(f"catalog profile is invalid: {profile}")
        if not {"devops-platform-contracts", "devops-core"} <= set(names):
            raise ValueError(f"catalog profile omits core contracts: {profile}")
    if set(profiles.get("all", [])) != set(skills):
        raise ValueError("catalog all profile does not contain every skill")
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--expected-archive-digest")
    args = parser.parse_args()
    try:
        archive_bytes = args.archive.read_bytes()
        if args.expected_archive_digest and (not DIGEST.match(args.expected_archive_digest) or sha256(archive_bytes) != args.expected_archive_digest):
            raise ValueError("archive digest does not match the trusted expectation")
        with zipfile.ZipFile(args.archive) as archive:
            names = archive.namelist()
            infos = archive.infolist()
            if len(names) != len(set(names)): raise ValueError("archive contains duplicate paths")
            normalized = [unicodedata.normalize("NFC", name).casefold() for name in names]
            if len(normalized) != len(set(normalized)): raise ValueError("archive contains case/Unicode-colliding paths")
            if len(infos) > 5000: raise ValueError("archive contains too many files")
            if any(not safe_name(name) for name in names): raise ValueError("archive contains an unsafe path")
            if sum(info.file_size for info in infos) > 50 * 1024 * 1024: raise ValueError("archive expands beyond the 50 MiB release limit")
            for info in infos:
                file_type = (info.external_attr >> 16) & 0o170000
                permissions = (info.external_attr >> 16) & 0o777
                expected_permissions = 0o755 if PurePosixPath(info.filename).name in SPECIAL_SKILL_FILES else 0o644
                if info.create_system != 3: raise ValueError(f"archive member creator system is non-canonical: {info.filename}")
                if info.is_dir() or file_type != 0o100000: raise ValueError(f"archive contains a non-regular file: {info.filename}")
                if permissions != expected_permissions: raise ValueError(f"archive member permissions are invalid: {info.filename}")
                if info.compress_type != zipfile.ZIP_STORED: raise ValueError(f"archive member compression is non-canonical: {info.filename}")
                if info.flag_bits & 0x1: raise ValueError(f"encrypted archive member is forbidden: {info.filename}")
                if info.file_size > 5 * 1024 * 1024: raise ValueError(f"archive member is too large: {info.filename}")
                if info.compress_size and info.file_size / info.compress_size > 200: raise ValueError(f"suspicious compression ratio: {info.filename}")
            if "RELEASE-MANIFEST.json" not in names: raise ValueError("release manifest is missing")
            manifest = json.loads(archive.read("RELEASE-MANIFEST.json"))
            if not isinstance(manifest, dict) or set(manifest) != MANIFEST_KEYS:
                raise ValueError("release manifest fields are invalid")
            if manifest.get("schema_version") != "1.0" or manifest.get("contract_version") != "v2":
                raise ValueError("release manifest contract metadata is invalid")
            if not all(isinstance(manifest.get(key), str) and manifest[key] for key in ("name", "version")):
                raise ValueError("release manifest identity is invalid")
            if manifest.get("license") != "Apache-2.0" or "LICENSE" not in names:
                raise ValueError("release license metadata or LICENSE file is missing")
            if manifest.get("excluded_source_classes") != EXPECTED_EXCLUDED:
                raise ValueError("release manifest exclusion policy is invalid")
            declared = manifest.get("files")
            if not isinstance(declared, list): raise ValueError("manifest files must be an array")
            for item in declared:
                if not isinstance(item, dict) or set(item) != FILE_KEYS:
                    raise ValueError("manifest file entry is invalid")
                if not isinstance(item.get("path"), str) or not safe_name(item["path"]) or not isinstance(item.get("sha256"), str) or not DIGEST.fullmatch(item["sha256"]):
                    raise ValueError("manifest file path or digest is invalid")
                if not isinstance(item.get("size"), int) or isinstance(item.get("size"), bool) or item["size"] < 0:
                    raise ValueError("manifest file size is invalid")
            declared_paths = [item["path"] for item in declared]
            if len(declared_paths) != len(set(declared_paths)):
                raise ValueError("manifest declares duplicate paths")
            expected = {item["path"]: item for item in declared}
            actual_names = set(names) - {"RELEASE-MANIFEST.json"}
            if set(expected) != actual_names: raise ValueError("archive contents do not exactly match the manifest")
            if not REQUIRED_ROOT_FILES <= actual_names:
                raise ValueError("release is missing required root documentation")
            if not REQUIRED_TOOL_FILES <= actual_names:
                raise ValueError("release is not self-contained for install and verification")
            for name, item in expected.items():
                data = archive.read(name)
                if item.get("sha256") != sha256(data) or item.get("size") != len(data): raise ValueError(f"integrity mismatch: {name}")
                if b"\r" in data: raise ValueError(f"non-canonical line endings: {name}")
            catalog = parse_catalog(archive.read("catalog.json"))
            if manifest.get("name") != catalog["name"] or manifest.get("version") != catalog["version"] or manifest.get("contract_version") != catalog["contract_version"]:
                raise ValueError("release manifest and catalog identity differ")
            skills = set(catalog["skills"])
            if any(not allowed_release_path(name, skills) for name in actual_names):
                raise ValueError("archive contains a path outside the catalog release allowlist")
            for skill in skills:
                required = {f"{skill}/SKILL.md", f"{skill}/module.yaml", f"{skill}/agents/openai.yaml"}
                if not required <= actual_names:
                    raise ValueError(f"archive skill is incomplete: {skill}")
            embedded_catalog = "devops-platform-contracts/catalog.json"
            embedded_requirements = "devops-platform-contracts/requirements.txt"
            if embedded_catalog not in actual_names or parse_catalog(archive.read(embedded_catalog)) != catalog:
                raise ValueError("root and embedded runtime catalogs differ")
            if embedded_requirements not in actual_names or archive.read(embedded_requirements) != archive.read("requirements.txt"):
                raise ValueError("root and embedded runtime requirements differ")
        print(f"OK: verified {args.archive} version={manifest.get('version')} files={len(expected)} archive_digest={sha256(archive_bytes)}")
        return 0
    except (OSError, KeyError, ValueError, json.JSONDecodeError, zipfile.BadZipFile) as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
