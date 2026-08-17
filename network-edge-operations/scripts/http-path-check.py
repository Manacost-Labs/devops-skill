#!/usr/bin/env python3
"""Read-only HTTP(S) path check using the Python standard library."""
from __future__ import annotations
import argparse, ipaddress, socket, ssl, time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler
from urllib.parse import urlsplit

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl): return None

def validate_url(url: str, allow_private: bool) -> None:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname: raise ValueError("URL must use http or https and include a hostname")
    if parsed.username or parsed.password: raise ValueError("credential-bearing URLs are forbidden")
    addresses = {item[4][0] for item in socket.getaddrinfo(parsed.hostname, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)}
    unsafe = [value for value in addresses if (address := ipaddress.ip_address(value)).is_private or address.is_loopback or address.is_link_local or address.is_multicast or address.is_reserved or address.is_unspecified]
    if unsafe and not allow_private: raise ValueError(f"private/special destination blocked ({', '.join(sorted(unsafe))}); use --allow-private only for an approved target")

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--allow-private", action="store_true", help="Permit an explicitly approved private/special target.")
    args = parser.parse_args()
    url = args.url
    request = Request(url, method="GET", headers={"User-Agent": "devops-edge-check/0.2"})
    started = time.monotonic()
    try:
        validate_url(url, args.allow_private)
        response = build_opener(NoRedirect).open(request, timeout=10)
        code, headers = response.status, response.headers
    except HTTPError as error:
        code, headers = error.code, error.headers
    except (OSError, URLError, ValueError, ssl.SSLError) as error:
        print(f"ERROR: request failed: {error}"); return 1
    elapsed = (time.monotonic() - started) * 1000
    print(f"url: {url}\nstatus: {code}\nlatency_ms: {elapsed:.0f}\nlocation: {headers.get('Location', '')}\nserver: {headers.get('Server', '')}")
    return 0 if 200 <= code < 400 else 1
if __name__ == "__main__": raise SystemExit(main())
