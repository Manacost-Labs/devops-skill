#!/usr/bin/env python3
"""Build a clean, allowlisted public source tree without private operation history."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    ".gitattributes",
    ".gitignore",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "GOVERNANCE.md",
    "LICENSE",
    "README.md",
    "SECURITY.md",
    "SUPPORT.md",
    "catalog.json",
    "requirements.txt",
}
PUBLIC_TREES = {".github", "docs", "evaluations", "examples", "tests"}
PUBLIC_TOOLS = {
    "tools/build_public_source.py",
    "tools/build_release.py",
    "tools/install.py",
    "tools/verify_release.py",
}
ALLOWED_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".py", ".ps1", ".sh", ".txt"}
SPECIAL_FILES = {"host-audit", "CODEOWNERS"}
FORBIDDEN_PARTS = {".git", "dist", "lab-artifacts", "operations", "__pycache__", ".pytest_cache", ".devops-skill-backups"}
TARGET_TOOL_PATTERNS = {
    "tools/bootstrap-*-nocloud.ps1",
    "tools/enable-codex-ssh-*.sh",
    "tools/install-codex-key-*.sh",
}
SECRET_PATTERNS = {
    "private key": re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "AWS access key": re.compile(rb"AKIA[0-9A-Z]{16}"),
    "GitHub token": re.compile(rb"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{50,})"),
    "GitLab token": re.compile(rb"glpat-[A-Za-z0-9_-]{20,}"),
    "Slack token": re.compile(rb"xox[baprs]-[A-Za-z0-9-]{20,}"),
    "Cloudflare account token": re.compile(rb"cfat_[A-Za-z0-9_-]{20,}"),
    "npm token": re.compile(rb"npm_[A-Za-z0-9]{30,}"),
}


def sha256(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def is_reparse_point(metadata: os.stat_result) -> bool:
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(metadata, "st_file_attributes", 0) & flag)


def require_regular_file(path: Path) -> None:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or is_reparse_point(metadata) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"public source must be a regular non-reparse file: {path}")
    resolved_root = ROOT.resolve(strict=True)
    resolved = path.resolve(strict=True)
    if resolved_root not in resolved.parents:
        raise ValueError(f"public source escapes repository root: {path}")


def safe_tree(folder: Path) -> list[Path]:
    if not folder.exists():
        return []
    metadata = folder.lstat()
    if stat.S_ISLNK(metadata.st_mode) or is_reparse_point(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"public source directory must be real and non-reparse: {folder}")
    files: list[Path] = []
    for directory, names, filenames in os.walk(folder, topdown=True, followlinks=False):
        current = Path(directory)
        names[:] = sorted(name for name in names if name not in FORBIDDEN_PARTS)
        for name in names:
            metadata = (current / name).lstat()
            if stat.S_ISLNK(metadata.st_mode) or is_reparse_point(metadata) or not stat.S_ISDIR(metadata.st_mode):
                raise ValueError(f"public source directory must be real and non-reparse: {current / name}")
        for name in sorted(filenames):
            path = current / name
            require_regular_file(path)
            files.append(path)
    return files


def public_files(catalog: dict) -> list[Path]:
    files: list[Path] = []
    for relative in sorted(ROOT_FILES | PUBLIC_TOOLS):
        path = ROOT / relative
        if not path.is_file():
            raise ValueError(f"required public source file is missing: {relative}")
        require_regular_file(path)
        files.append(path)
    for tree in sorted(PUBLIC_TREES):
        files.extend(safe_tree(ROOT / tree))
    for skill in sorted(catalog["skills"]):
        files.extend(safe_tree(ROOT / skill))
    unique = sorted(set(files), key=lambda path: path.relative_to(ROOT).as_posix())
    if len(unique) != len(files):
        raise ValueError("public source allowlist contains duplicate paths")
    return unique


def validate_relative(relative: Path) -> None:
    if any(part in FORBIDDEN_PARTS for part in relative.parts):
        raise ValueError(f"forbidden private path selected: {relative.as_posix()}")
    if any(relative.match(pattern) for pattern in TARGET_TOOL_PATTERNS):
        raise ValueError(f"target-specific path selected: {relative.as_posix()}")
    if len(relative.parts) == 1 and relative.name in ROOT_FILES:
        return
    if relative.suffix.lower() not in ALLOWED_SUFFIXES and relative.name not in SPECIAL_FILES:
        raise ValueError(f"unexpected public source file type: {relative.as_posix()}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        output = args.output.resolve()
        root = ROOT.resolve(strict=True)
        if output == root or root in output.parents:
            raise ValueError("public export output must be outside the source repository")
        if output.exists() and any(output.iterdir()):
            raise ValueError("public export output directory must be absent or empty")
        if output.exists():
            metadata = output.lstat()
            if stat.S_ISLNK(metadata.st_mode) or is_reparse_point(metadata) or not stat.S_ISDIR(metadata.st_mode):
                raise ValueError("public export output must be a real non-reparse directory")
        catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8-sig"))
        validation = subprocess.run(
            [sys.executable, str(ROOT / "devops-platform-contracts/scripts/validate_platform.py")],
            cwd=ROOT,
        )
        if validation.returncode:
            raise ValueError("platform validation failed; public export was not built")
        entries = []
        payloads: dict[Path, bytes] = {}
        for source in public_files(catalog):
            relative = source.relative_to(ROOT)
            validate_relative(relative)
            data = source.read_bytes().replace(b"\r\n", b"\n")
            if b"\r" in data:
                raise ValueError(f"stray CR character in public source file {relative.as_posix()}")
            for label, pattern in SECRET_PATTERNS.items():
                if pattern.search(data):
                    raise ValueError(f"possible {label} in public source file {relative.as_posix()}")
            payloads[relative] = data
            entries.append({"path": relative.as_posix(), "sha256": sha256(data), "size": len(data)})
        entries.sort(key=lambda item: item["path"])
        output.mkdir(parents=True, exist_ok=True)
        for relative, data in payloads.items():
            destination = output / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        manifest = {
            "schema_version": "1.0",
            "name": catalog["name"],
            "version": catalog["version"],
            "files": entries,
            "excluded": ["git-history", "operations", "lab-artifacts", "target-specific-tools", "credentials", "release-archives"],
        }
        manifest_data = json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8") + b"\n"
        (output / "PUBLIC-SOURCE-MANIFEST.json").write_bytes(manifest_data)
        print(f"OK: built public source tree {output} files={len(entries)} manifest_digest={sha256(manifest_data)}")
        return 0
    except (OSError, ValueError, json.JSONDecodeError, KeyError) as error:
        print(f"ERROR: {error}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
