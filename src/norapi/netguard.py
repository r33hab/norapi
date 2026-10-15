"""Guards for URLs the registry fetches on behalf of third-party metadata.

Catalogue entries and curated YAML both carry URLs the spec fetcher and the link checker will
request. Those requests must never reach private networks (SSRF) and must never pull unbounded
bodies. Every fetcher goes through `get_capped`, which:

- accepts http(s) only and resolves the host itself, refusing any address that is not globally
  routable (loopback, private ranges, link-local such as cloud metadata, multicast);
- connects to the exact address it validated, so a DNS answer cannot change between the check
  and the connect (rebinding). The hostname is kept for TLS verification (SNI) and the Host header;
- follows redirects by hand, validating every hop the same way before requesting it;
- reads the body through a streamed cap instead of buffering an unknown size first.
"""

from __future__ import annotations

import ipaddress
import socket
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx

MAX_BODY_BYTES = 8 * 1024 * 1024
MAX_REDIRECTS = 5
_BLOCKED_SUFFIXES = (".local", ".internal", ".localhost")


@dataclass(frozen=True)
class PinnedTarget:
    """A validated destination: the logical host for TLS and Host, and the address to connect to."""

    host: str
    port: int
    connect_host: str


def resolve_public(url: str) -> PinnedTarget | None:
    """Resolve and validate a URL's host. None when it is not a public http(s) destination."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return None
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return None
    host = parsed.hostname
    if host == "localhost" or host.endswith(_BLOCKED_SUFFIXES):
        return None
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return None
    try:
        addresses = [ipaddress.ip_address(host)]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        except (socket.gaierror, UnicodeError):
            return None
        addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
    if not addresses or not all(_is_global(ip) for ip in addresses):
        return None
    return PinnedTarget(host=host, port=port, connect_host=str(addresses[0]))


def is_public_url(url: str) -> bool:
    return resolve_public(url) is not None


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


def _pinned_url(url: str, target: PinnedTarget) -> str:
    parsed = urlparse(url)
    if target.connect_host == target.host:
        return url
    netloc = f"[{target.connect_host}]" if ":" in target.connect_host else target.connect_host
    if parsed.port:
        netloc += f":{parsed.port}"
    return parsed._replace(netloc=netloc).geturl()


def get_capped(
    client: httpx.Client,
    url: str,
    headers: dict[str, str] | None = None,
    limit: int = MAX_BODY_BYTES,
) -> tuple[httpx.Response, bytes | None, str] | None:
    """GET a public URL with a body cap: (response, body, final_url), or None when blocked.

    `final_url` is the logical URL after redirects (the one to resolve relative links against);
    `response.url` may carry the pinned address instead and should not be shown to anyone.
    """
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        target = resolve_public(current)
        if target is None:
            return None
        parsed = urlparse(current)
        request_headers = {**(headers or {}), "Host": parsed.netloc}
        with client.stream(
            "GET",
            _pinned_url(current, target),
            headers=request_headers,
            extensions={"sni_hostname": target.host},
            follow_redirects=False,
        ) as response:
            location = response.headers.get("location")
            if response.is_redirect and location:
                current = urljoin(current, location)
                continue
            body = read_capped(response, limit)
        return response, body, current
    return None
