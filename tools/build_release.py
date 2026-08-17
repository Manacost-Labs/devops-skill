#!/usr/bin/env python3
"""Build a deterministic, allowlisted DevOps skill release archive."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EPOCH = (1980, 1, 1, 0, 0, 0)
ROOT_FILES = {
    "catalog.json",
    "requirements.txt",
    "README.md",
    "SECURITY.md",
    "LICENSE",
    "CONTRIBUTING.md",
    "GOVERNANCE.md",
    "SUPPORT.md",
    "CHANGELOG.md",
}
TOOL_FILES = {
    "tools/devops_exec.py",
    "tools/install.py",
    "tools/verify_release.py",
}
ALLOWED_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".py", ".ps1", ".txt"}
SECRET_PATTERNS = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "GitHub token": re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})"),
    "GitLab token": re.compile(rb"glpat-[A-Za-z0-9_-]{20,}"),
    "Slack token": re.compile(rb"xox[baprs]-[A-Za-z0-9-]{20,}"),
    "Cloudflare account token": re.compile(rb"cfat_[A-Za-z0-9_-]{20,}"),
    "npm token": re.compile(rb"npm_[A-Za-z0-9]{30,}"),
}


def digest(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def is_reparse_point(metadata: os.stat_result) -> bool:
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(metadata, "st_file_attributes", 0) & flag)


def resolved_inside(path: Path, root: Path) -> Path:
    resolved_root = root.resolve(strict=True)
    resolved = path.resolve(strict=True)
    if resolved != resolved_root and resolved_root not in resolved.parents:
        raise ValueError(f"release source escapes its root: {path}")
    return resolved


def require_real_directory(path: Path, root: Path) -> None:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or is_reparse_point(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"release source directory must be real and non-reparse: {path}")
    resolved_inside(path, root)


def require_regular_file(path: Path, root: Path) -> None:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or is_reparse_point(metadata) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"release source must be a regular non-reparse file: {path}")
    resolved_inside(path, root)


def safe_tree_files(folder: Path) -> list[Path]:
    require_real_directory(folder, ROOT)
    files: list[Path] = []
    for directory, names, filenames in os.walk(folder, topdown=True, followlinks=False):
        current = Path(directory)
        require_real_directory(current, ROOT)
        for name in names:
            require_real_directory(current / name, ROOT)
        for name in filenames:
            path = current / name
            require_regular_file(path, ROOT)
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def safe_read(path: Path) -> bytes:
    require_regular_file(path, ROOT)
    return path.read_bytes()


def files_for_release(catalog: dict) -> list[Path]:
    require_real_directory(ROOT, ROOT)
    missing = sorted(name for name in ROOT_FILES if not (ROOT / name).is_file())
    if missing:
        raise ValueError(f"required release files are missing: {', '.join(missing)}")
    files = []
    for name in sorted(ROOT_FILES):
        path = ROOT / name
        require_regular_file(path, ROOT)
        files.append(path)
    docs = ROOT / "docs"
    for path in safe_tree_files(docs):
        if path.suffix.lower() != ".md":
            raise ValueError(f"unexpected documentation file type: {path.relative_to(ROOT)}")
        files.append(path)
    for relative in sorted(TOOL_FILES):
        path = ROOT / relative
        require_regular_file(path, ROOT)
        files.append(path)
    for skill in sorted(catalog["skills"]):
        folder = ROOT / skill
        for path in safe_tree_files(folder):
            if "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            if path.suffix.lower() not in ALLOWED_SUFFIXES and path.name not in {"host-audit"}:
                raise ValueError(f"unexpected runtime file type: {path.relative_to(ROOT)}")
            files.append(path)
    return sorted(files, key=lambda path: path.relative_to(ROOT).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        require_real_directory(ROOT, ROOT)
        catalog = json.loads(safe_read(ROOT / "catalog.json").decode("utf-8-sig"))
        paths = files_for_release(catalog)
        if len(paths) != len(set(paths)):
            raise ValueError("release allowlist contains duplicate paths")
        validation = subprocess.run([sys.executable, str(ROOT / "devops-platform-contracts/scripts/validate_platform.py")], cwd=ROOT)
        if validation.returncode:
            print("ERROR: platform validation failed; no release built")
            return 1
        entries = []
        payloads = {}
        for path in paths:
            relative = path.relative_to(ROOT).as_posix()
            data = safe_read(path).replace(b"\r\n", b"\n")
            if b"\r" in data: raise ValueError(f"stray CR character in {relative}")
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(data): raise ValueError(f"possible {label} in release file {relative}")
            payloads[relative] = data
            entries.append({"path": relative, "sha256": digest(data), "size": len(data)})
        entries.sort(key=lambda item: item["path"])
        manifest = {
            "schema_version": "1.0",
            "name": catalog["name"],
            "version": catalog["version"],
            "contract_version": catalog["contract_version"],
            "license": "Apache-2.0",
            "files": entries,
            "excluded_source_classes": [".git", "lab-artifacts", "operations", "tests", "target-specific-tools", "development-only-tools", "caches", "credentials"]
        }
        manifest_bytes = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        # STORE avoids zlib-version differences, making identical source bytes reproducible across builders.
        with zipfile.ZipFile(args.output, "w", compression=zipfile.ZIP_STORED) as archive:
            for relative, data in sorted(payloads.items()):
                info = zipfile.ZipInfo(relative, EPOCH)
                info.create_system = 3
                mode = 0o100755 if Path(relative).name == "host-audit" else 0o100644
                info.external_attr = mode << 16
                info.compress_type = zipfile.ZIP_STORED
                archive.writestr(info, data)
            info = zipfile.ZipInfo("RELEASE-MANIFEST.json", EPOCH)
            info.create_system = 3
            info.external_attr = 0o100644 << 16
            info.compress_type = zipfile.ZIP_STORED
            archive.writestr(info, manifest_bytes)
        print(f"OK: built {args.output} files={len(entries)} digest={digest(args.output.read_bytes())}")
        print("NOTE: this manifest verifies archive integrity but is not a signature or SLSA provenance.")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, KeyError) as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
