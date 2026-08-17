#!/usr/bin/env python3
"""Read-only repeated HTTP deployment verification."""
from __future__ import annotations
import argparse, ipaddress, socket, time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None

def validate_url(url: str, allow_private: bool) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname: raise ValueError("URL must use http or https and include a hostname")
    if parsed.username or parsed.password: raise ValueError("credential-bearing URLs are forbidden")
    addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    unsafe = [value for value in addresses if (address := ipaddress.ip_address(value)).is_private or address.is_loopback or address.is_link_local or address.is_multicast or address.is_reserved or address.is_unspecified]
    if unsafe and not allow_private: raise ValueError("private/special destination blocked; use --allow-private only for an approved target")

def check(url: str) -> tuple[int, float]:
    started = time.monotonic()
    try:
        with build_opener(NoRedirect).open(Request(url, headers={"User-Agent": "devops-deploy-verify/0.2"}), timeout=10) as response:
            return response.status, (time.monotonic() - started) * 1000
    except HTTPError as error: return error.code, (time.monotonic() - started) * 1000
    except URLError: return 0, (time.monotonic() - started) * 1000

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--attempts", type=int, default=3)
    parser.add_argument("--allow-private", action="store_true", help="Permit an explicitly approved private/special target.")
    args = parser.parse_args()
    if not 1 <= args.attempts <= 20: print("ERROR: attempts must be 1-20"); return 2
    try: validate_url(args.url, args.allow_private)
    except (OSError, ValueError) as error: print(f"ERROR: {error}"); return 2
    results = [check(args.url) for _ in range(args.attempts)]
    for i, (code, ms) in enumerate(results, 1): print(f"attempt={i} status={code} latency_ms={ms:.0f}")
    good = sum(1 for code, _ in results if 200 <= code < 400)
    print(f"success_rate={good}/{attempts}")
    return 0 if good == attempts else 1
if __name__ == "__main__": raise SystemExit(main())
