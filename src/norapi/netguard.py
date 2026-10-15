"""Guards for URLs the registry fetches on behalf of third-party metadata.

Catalogue entries and curated YAML both carry URLs the harvester, the spec fetcher and the link
checker will request. Those requests must never reach private networks (SSRF) and must never
pull unbounded bodies. Both guards live here so every fetcher applies the same rule.
"""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

import httpx

MAX_BODY_BYTES = 8 * 1024 * 1024


def is_public_url(url: str) -> bool:
    """True for http(s) URLs whose host resolves only to globally routable addresses."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    host = parsed.hostname
    if host in ("localhost",) or host.endswith(".local") or host.endswith(".internal"):
        return False
    try:
        candidates = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, parsed.port or 443, proto=socket.IPPROTO_TCP)
        except socket.gaierror:
            return False
        candidates = [ipaddress.ip_address(info[4][0]) for info in infos]
    return bool(candidates) and all(_is_global(ip) for ip in candidates)


def _is_global(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def read_capped(response: httpx.Response, limit: int = MAX_BODY_BYTES) -> bytes | None:
    """Read a streamed response body up to `limit` bytes; None when the body is larger."""
    chunks: list[bytes] = []
    size = 0
    for chunk in response.iter_bytes():
        size += len(chunk)
        if size > limit:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def get_capped(
    client: httpx.Client,
    url: str,
    headers: dict[str, str] | None = None,
    limit: int = MAX_BODY_BYTES,
) -> tuple[httpx.Response, bytes | None] | None:
    """GET a public URL with a body cap: (response, body), or None when the URL is not public.

    Redirect targets are checked too: a public host must not bounce the fetcher into a private one.
    """
    if not is_public_url(url):
        return None
    with client.stream("GET", url, headers=headers) as response:
        for hop in response.history:
            if not is_public_url(str(hop.url)):
                return None
        if not is_public_url(str(response.url)):
            return None
        body = read_capped(response, limit)
    return response, body
