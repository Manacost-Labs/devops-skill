"""Provision only the pinned Oracle decoder and its private TLS libraries for CI."""
from __future__ import annotations

import hashlib
import shutil
import tarfile
from pathlib import Path
from urllib.parse import urlsplit
from urllib.request import urlopen

VERSION = "8.4.13"
BUNDLE = f"mysql-{VERSION}-linux-glibc2.28-x86_64-minimal"
URL = f"https://cdn.mysql.com/Downloads/MySQL-8.4/{BUNDLE}.tar.xz"
# Retrieved from Oracle's HTTPS CDN and pinned during review, 2026-10-29.
SHA256 = "5dfbb764f731df40ef9e4f5d69aed32bdac8ba1af20bd96b7d40a942d83d4ed2"
SIZE = 79_753_532


def provision(folder: Path) -> Path:
    folder.mkdir()
    archive = folder/"vendor.tar.xz"
    digest = hashlib.sha256()
    with urlopen(URL, timeout=60) as response, archive.open("xb") as output:
        endpoint = urlsplit(response.geturl())
        if endpoint.scheme != "https" or endpoint.hostname != "cdn.mysql.com":
            raise ValueError("unexpected Oracle download endpoint")
        remaining = SIZE
        while remaining:
            block = response.read(min(1 << 20, remaining))
            if not block: raise ValueError("truncated Oracle client bundle")
            output.write(block); digest.update(block); remaining -= len(block)
        if response.read(1): raise ValueError("oversized Oracle client bundle")
    if digest.hexdigest() != SHA256:
        raise ValueError("Oracle client bundle digest mismatch")
    # Fixed regular members only: no archive paths, symlinks, scripts or server install.
    wanted = ("bin/mysqlbinlog", "lib/private/libssl.so.3", "lib/private/libcrypto.so.3")
    with tarfile.open(archive) as bundle:
        for relative in wanted:
            member = bundle.getmember(f"{BUNDLE}/{relative}")
            if not member.isfile() or not 0 < member.size <= 32 << 20:
                raise ValueError("unexpected Oracle tool member")
            destination = folder/relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            with bundle.extractfile(member) as source, destination.open("xb") as output:
                shutil.copyfileobj(source, output, length=1 << 20)
            destination.chmod(0o755 if relative.startswith("bin/") else 0o644)
    return folder/"bin/mysqlbinlog"
