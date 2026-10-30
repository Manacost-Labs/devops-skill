#!/usr/bin/env python3
"""Bounded single-hop diagnostic: pinned address, verified TLS, no proxy/redirect."""
from __future__ import annotations

import argparse
import http.client
import ipaddress
import socket
import ssl
import time
from urllib.parse import quote, urljoin, urlsplit


def destination(value, allow_private):
    address = ipaddress.ip_address(value)
    effective = address.ipv4_mapped if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped else address
    if (effective.is_link_local or effective.is_multicast or effective.is_unspecified
            or effective.is_reserved or str(effective) == "fd00:ec2::254"):
        raise ValueError("metadata/link-local or unroutable destination forbidden")
    if not effective.is_global and not allow_private:
        raise ValueError("private/special destination blocked; explicit approved target requires --allow-private")
    return address


def resolve_target(url, allow_private=False, connect_ip=None):
    if len(url) > 8192 or any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in url) or "\\" in url:
        raise ValueError("invalid URL characters or length")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must use http or https and include a hostname")
    if parsed.username is not None or parsed.password is not None:
        raise ValueError("credential-bearing URLs are forbidden")
    host = parsed.hostname.encode("idna").decode("ascii").lower()
    if "%" in host or host.rstrip(".") in {"metadata", "instance-data", "metadata.google.internal"}:
        raise ValueError("metadata or scoped-address hostname forbidden")
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not 1 <= port <= 65535:
        raise ValueError("invalid port")
    values = [connect_ip] if connect_ip else [item[4][0] for item in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)]
    addresses = list(dict.fromkeys(destination(value, allow_private) for value in values))
    if not addresses or len(addresses) > 32:
        raise ValueError("empty or excessive destination set")
    return parsed, host, port, addresses


def origin(url):
    """Never print paths, queries, fragments or credential-bearing locations."""
    try:
        parsed = urlsplit(url)
        if parsed.username is not None or parsed.password is not None:
            return "[credential-bearing location suppressed]"
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return "[invalid location suppressed]"
        host = parsed.hostname.encode("idna").decode("ascii")
        host = "[" + host + "]" if ":" in host else host
        return parsed.scheme + "://" + host + (":" + str(parsed.port) if parsed.port else "") + "/[path-query-suppressed]"
    except (ValueError, UnicodeError):
        return "[invalid location suppressed]"


def safe_header(value):
    return "".join(char if 32 <= ord(char) <= 126 else "?" for char in value[:160])


def request_once(url, *, allow_private=False, connect_ip=None, ca_file=None):
    started = time.monotonic()
    deadline = started + 10
    parsed, host, port, addresses = resolve_target(url, allow_private, connect_ip)
    context = ssl.create_default_context(cafile=ca_file) if parsed.scheme == "https" else None
    path = quote(parsed.path or "/", safe="/%:@!$&'()*+,;=-._~")
    if parsed.query:
        path += "?" + quote(parsed.query, safe="%:@!$&'()*+,;=/?-._~")
    last_error = None
    for address in addresses:
        connection = http.client.HTTPConnection(host, port, timeout=10)
        transport = None
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("observation deadline")
            transport = socket.socket(socket.AF_INET6 if address.version == 6 else socket.AF_INET, socket.SOCK_STREAM)
            transport.settimeout(remaining)
            # Numeric socket.connect never resolves the approved hostname again.
            transport.connect((str(address), port))
            if context is not None:
                transport = context.wrap_socket(transport, server_hostname=host)
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("observation deadline")
            transport.settimeout(remaining)
            connection.sock = transport
            connection.request("GET", path, headers={"User-Agent": "devops-edge-check/0.3", "Connection": "close"})
            response = connection.getresponse()
            return {"status": response.status, "address": str(address), "latency_ms": round((time.monotonic() - started) * 1000),
                    "location": origin(urljoin(url, response.getheader("Location"))) if response.getheader("Location") else "",
                    "server": safe_header(response.getheader("Server", ""))}
        except ssl.SSLError:
            raise  # Never try a different endpoint to bypass a TLS failure.
        except OSError as error:
            last_error = error
        finally:
            connection.close()
            if transport is not None:
                transport.close()
    raise OSError("no approved destination responded") from last_error


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("--allow-private", action="store_true", help="Allow approved private targets, never metadata/link-local/special destinations.")
    parser.add_argument("--connect-ip", help="Explicit approved numeric endpoint; preserve URL Host and TLS SNI/name verification.")
    parser.add_argument("--ca-file", help="Explicit approved CA trust file for private PKI; certificate validation stays enabled.")
    args = parser.parse_args()
    try:
        result = request_once(args.url, allow_private=args.allow_private, connect_ip=args.connect_ip, ca_file=args.ca_file)
    except ssl.SSLCertVerificationError as error:
        print(f"ERROR: TLS certificate verification failed; verify_code={error.verify_code}")
        return 1
    except ssl.SSLError:
        print("ERROR: TLS handshake failed")
        return 1
    except (ValueError, UnicodeError) as error:
        print("ERROR: " + safe_header(str(error)))
        return 1
    except (OSError, http.client.HTTPException):
        print("ERROR: connection or HTTP response failed")
        return 1
    print("url: " + origin(args.url))
    for key, value in result.items():
        print(f"{key}: {value}")
    print("redirect_followed: false\nproxy: disabled\ncompleteness: single-hop-only")
    return 0 if 200 <= result["status"] < 400 else 1


if __name__ == "__main__":
    raise SystemExit(main())
