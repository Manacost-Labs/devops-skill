#!/usr/bin/env python3
"""Install a validated DevOps skill profile; dry-run unless --apply is passed."""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, os, shutil, stat, subprocess, sys, tempfile
from datetime import datetime, timezone
from contextlib import nullcontext
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_support_spec = importlib.util.spec_from_file_location("installation_runtime_support", ROOT / "tools/runtime_lock.py")
_support = importlib.util.module_from_spec(_support_spec)
_support_spec.loader.exec_module(_support)


def is_reparse_point(metadata: os.stat_result) -> bool:
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(metadata, "st_file_attributes", 0) & flag)


def real_directory(path: Path) -> None:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or is_reparse_point(metadata) or not stat.S_ISDIR(metadata.st_mode):
        raise ValueError(f"directory must be real and non-reparse: {path}")


def real_file(path: Path) -> None:
    metadata = path.lstat()
    if stat.S_ISLNK(metadata.st_mode) or is_reparse_point(metadata) or not stat.S_ISREG(metadata.st_mode):
        raise ValueError(f"file must be regular and non-reparse: {path}")


def tree_digest(root: Path) -> str:
    real_directory(root)
    digest = hashlib.sha256()
    for directory, names, filenames in os.walk(root, topdown=True, followlinks=False):
        current = Path(directory)
        real_directory(current)
        names.sort()
        filenames.sort()
        for name in names:
            real_directory(current / name)
        for name in filenames:
            path = current / name
            real_file(path)
            digest.update(path.relative_to(root).as_posix().encode("utf-8") + b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def path_exists(path: Path) -> bool:
    return os.path.lexists(path)


def rollback_profile(touched: list[str], committed: set[str], destinations: dict[str, Path], backups: dict[str, Path | None], failed_root: Path) -> list[str]:
    errors: list[str] = []
    failed_root.mkdir(parents=True, exist_ok=True)
    for name in reversed(touched):
        destination = destinations[name]
        backup = backups.get(name)
        try:
            if name in committed and path_exists(destination):
                failed = failed_root / name
                if path_exists(failed):
                    raise ValueError(f"failed-copy collision: {failed}")
                os.replace(destination, failed)
            if backup and path_exists(backup):
                if path_exists(destination):
                    raise ValueError(f"destination occupied while restoring {name}; previous copy remains at {backup}")
                os.replace(backup, destination)
        except Exception as error:
            errors.append(f"{name}: {error}")
    return errors


def install_runtime(args) -> int:
    """Install the allowlisted, complete execution runtime as one recoverable unit."""
    if args.destination is None:
        print("ERROR: --runtime requires an explicit --destination outside the source checkout")
        return 2
    if args.profile not in {None, "all"}:
        print("ERROR: --runtime contains all modules; profiles select separately installed instructions")
        return 2
    if args.force and not args.apply:
        print("ERROR: --force requires --apply")
        return 2
    source = ROOT.resolve()
    destination = args.destination.expanduser().resolve()
    if destination == source or source in destination.parents or destination in source.parents or destination == Path(destination.anchor):
        print("ERROR: runtime destination must be separate from the source and its ancestors")
        return 2
    try:
        if path_exists(args.destination.expanduser()):
            real_directory(args.destination.expanduser())
        with _support.runtime_lock(destination) if args.apply else nullcontext():
            existed = destination.exists()
            original_digest = tree_digest(destination) if existed else None
            if existed and any(destination.iterdir()):
                marker = destination / "catalog.json"
                identity = json.loads(marker.read_text(encoding="utf-8-sig")) if marker.is_file() else None
                if not isinstance(identity, dict) or identity.get("name") != "devops-skill-platform" or not (destination / "tools/install.py").is_file():
                    raise ValueError("refusing to replace a non-runtime directory")
            if existed and not args.force:
                raise ValueError("destination already exists; review then use --apply --force")
            spec = importlib.util.spec_from_file_location("runtime_release_paths", source / "tools/verify_release.py")
            verifier = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(verifier)
            catalog = json.loads((source / "catalog.json").read_text(encoding="utf-8-sig"))
            files = [source / name for name in sorted(verifier.REQUIRED_ROOT_FILES | verifier.REQUIRED_TOOL_FILES)]
            real_directory(source / "tools")
            real_directory(source / "tools/hooks")
            for folder in [source / "docs", *(source / name for name in sorted(catalog["skills"]))]:
                real_directory(folder)
                for directory, names, filenames in os.walk(folder, followlinks=False):
                    names[:] = sorted(name for name in names if name not in {"__pycache__", ".pytest_cache"})
                    for name in names:
                        real_directory(Path(directory) / name)
                    for name in sorted(filenames):
                        path = Path(directory) / name
                        if path.suffix == ".pyc":
                            continue
                        if not verifier.allowed_release_path(path.relative_to(source).as_posix(), set(catalog["skills"])):
                            raise ValueError(f"unexpected runtime member: {path.relative_to(source)}")
                        files.append(path)
            # Match tree_digest's directory-first os.walk order.
            files.sort(key=lambda path: (path.parent.relative_to(source).parts, path.name))
            def snapshot():
                digest = hashlib.sha256()
                for path in files:
                    real_file(path)
                    if source not in path.resolve().parents:
                        raise ValueError("runtime member escapes the source")
                    digest.update(path.relative_to(source).as_posix().encode("utf-8") + b"\0")
                    digest.update(path.read_bytes())
                return digest.hexdigest()
            expected = snapshot()
            print(f"runtime: {len(files)} allowlisted files -> {destination}")
            print("Includes planner, executor, optional Claude hook, verifier and all 22 modules; hook settings are not enabled automatically.")
            if not args.apply:
                print("Dry-run only. Review then add --apply.")
                return 0
            destination.parent.mkdir(parents=True, exist_ok=True)
            real_directory(destination.parent)
            with tempfile.TemporaryDirectory(prefix=".devops-runtime-stage-", dir=destination.parent) as staging:
                staged = Path(staging) / "runtime"
                staged.mkdir()
                for path in files:
                    target = staged / path.relative_to(source)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
                if tree_digest(staged) != expected or snapshot() != expected:
                    raise ValueError("runtime source or staged content changed")
                validation = subprocess.run([sys.executable, str(staged / "devops-platform-contracts/scripts/validate_platform.py")], capture_output=True, text=True)
                if validation.returncode:
                    raise ValueError("staged runtime validation failed")
                # Keep local operation plans and audit history across upgrades.
                if existed and (destination / "operations").exists():
                    tree_digest(destination / "operations")
                    shutil.copytree(destination / "operations", staged / "operations")
                if path_exists(destination) != existed or (existed and tree_digest(destination) != original_digest):
                    raise ValueError("runtime destination changed concurrently")
                staged_digest = tree_digest(staged)
                backup_parent = destination.parent / ".devops-skill-backups"
                backup_parent.mkdir(exist_ok=True)
                real_directory(backup_parent)
                backup_set = Path(tempfile.mkdtemp(prefix="runtime-", dir=backup_parent))
                previous = backup_set / "previous"
                moved_previous = installed = False
                try:
                    if existed:
                        os.replace(destination, previous)
                        moved_previous = True
                    os.replace(staged, destination)
                    installed = True
                    if tree_digest(destination) != staged_digest:
                        raise ValueError("installed runtime digest mismatch")
                except Exception:
                    print(f"recovery-set: {backup_set}")
                    if installed:
                        os.replace(destination, backup_set / "failed")
                    if moved_previous:
                        os.replace(previous, destination)
                    raise
                print(f"OK: installed complete runtime at {destination}")
                print(f"backup-set: {backup_set}")
                print(f"Run from any project with an absolute path: python \"{destination / 'tools/devops_plan.py'}\" --help")
                return 0
    except (OSError, ValueError) as error:
        print(f"ERROR: runtime installation failed: {error}")
        return 1

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--profile")
    parser.add_argument("--destination", type=Path)
    parser.add_argument("--runtime", action="store_true", help="Install a complete execution runtime, not just skill instructions; requires --destination.")
    parser.add_argument("--apply", action="store_true", help="Copy files; otherwise print a dry-run.")
    parser.add_argument("--force", action="store_true", help="Allow replacing existing selected skills; requires --apply.")
    args = parser.parse_args()
    validation = subprocess.run([sys.executable, str(ROOT / "devops-platform-contracts/scripts/validate_platform.py")], cwd=ROOT, capture_output=True, text=True)
    if validation.returncode:
        print("ERROR: source platform validation failed; no installation attempted")
        print(validation.stdout + validation.stderr)
        return 1
    if args.runtime:
        return install_runtime(args)
    args.profile = args.profile or "web-linux"
    args.destination = args.destination or Path.home() / ".codex" / "skills"
    catalog = json.loads((ROOT / "catalog.json").read_text(encoding="utf-8-sig"))
    names = catalog.get("profiles", {}).get(args.profile)
    if names is None: print(f"ERROR: unknown profile {args.profile}"); return 2
    if args.force and not args.apply: print("ERROR: --force requires --apply"); return 2
    raw_destination_root = args.destination.expanduser()
    if path_exists(raw_destination_root):
        try: real_directory(raw_destination_root)
        except (OSError, ValueError) as error: print(f"ERROR: {error}"); return 1
    destination_root = raw_destination_root.resolve()
    try: real_directory(ROOT)
    except (OSError, ValueError) as error: print(f"ERROR: {error}"); return 1
    source_root = ROOT.resolve()
    plans = []
    for name in names:
        source_path = source_root / name
        destination = destination_root / name
        if source_path.parent != source_root or destination.parent != destination_root: print("ERROR: unsafe package path"); return 2
        try:
            real_directory(source_path)
            source = source_path.resolve(strict=True)
            if source.parent != source_root: raise ValueError(f"source skill escapes package root: {name}")
            source_digest = tree_digest(source)
            existed = path_exists(destination)
            destination_digest = None
            if existed:
                real_directory(destination)
                destination_digest = tree_digest(destination)
        except (OSError, ValueError) as error:
            print(f"ERROR: {error}"); return 1
        action = "replace" if existed else "install"
        print(f"{action}: {name} -> {destination}")
        plans.append({"name": name, "source": source, "source_digest": source_digest, "destination": destination, "existed": existed, "destination_digest": destination_digest})
    if args.apply and any(plan["existed"] for plan in plans) and not args.force:
        print("ERROR: one or more destinations exist; rerun with --apply --force after review."); return 1
    if not args.apply:
        print("Skills only: execution tools and hook settings are not installed. Use --runtime --destination <separate-path> for the execution runtime.")
        print("Dry-run only. Review then add --apply; use --force only for intentional replacement.")
        return 0
    try:
        destination_root.mkdir(parents=True, exist_ok=True)
        real_directory(destination_root)
        with tempfile.TemporaryDirectory(prefix=".devops-skill-stage-", dir=destination_root) as staging_text:
            staging_root = Path(staging_text)
            staged: dict[str, Path] = {}
            for plan in plans:
                target = staging_root / plan["name"]
                shutil.copytree(plan["source"], target, symlinks=True)
                if tree_digest(target) != plan["source_digest"]:
                    raise ValueError(f"staged copy digest mismatch for {plan['name']}")
                staged[plan["name"]] = target

            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup_parent = destination_root / ".devops-skill-backups"
            backup_parent.mkdir(exist_ok=True)
            real_directory(backup_parent)
            transaction_root = Path(tempfile.mkdtemp(prefix=f"profile-{args.profile}-{stamp}-", dir=backup_parent))
            previous_root, failed_root = transaction_root / "previous", transaction_root / "failed"
            previous_root.mkdir(); failed_root.mkdir()
            destinations = {plan["name"]: plan["destination"] for plan in plans}
            backups: dict[str, Path | None] = {}
            touched: list[str] = []
            committed: set[str] = set()
            try:
                for plan in plans:
                    name, destination = plan["name"], plan["destination"]
                    current_exists = path_exists(destination)
                    if current_exists != plan["existed"]:
                        raise ValueError(f"destination changed concurrently before commit: {name}")
                    if current_exists and tree_digest(destination) != plan["destination_digest"]:
                        raise ValueError(f"destination content changed concurrently before commit: {name}")
                    backup = previous_root / name if current_exists else None
                    backups[name] = backup
                    if backup:
                        os.replace(destination, backup)
                        touched.append(name)
                    os.replace(staged[name], destination)
                    if name not in touched: touched.append(name)
                    committed.add(name)
                    if tree_digest(destination) != plan["source_digest"]:
                        raise ValueError(f"installed copy digest mismatch for {name}")
            except Exception as error:
                rollback_errors = rollback_profile(touched, committed, destinations, backups, failed_root)
                print(f"ERROR: profile installation failed; rollback attempted for every touched skill: {error}")
                print(f"recovery-set: {transaction_root}")
                if rollback_errors:
                    print("ERROR: rollback incomplete: " + "; ".join(rollback_errors))
                return 1
            print(f"OK: installed profile {args.profile} transactionally ({len(plans)} skill(s)).")
            print(f"backup-set: {transaction_root} (retain until the profile is accepted)")
            return 0
    except Exception as error:
        print(f"ERROR: profile staging failed before commit: {error}")
        return 1
if __name__ == "__main__": raise SystemExit(main())
