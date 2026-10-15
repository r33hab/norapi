"""Guards for URLs the registry fetches on behalf of third-party metadata.

Catalogue entries and curated YAML both carry URLs the spec fetcher and the link checker will
request. Those requests must never reach private networks (SSRF) and must never pull unbounded
bodies. Two pieces enforce that:

- `public_client()` builds an httpx client whose TCP layer resolves each hostname itself,
  refuses any address that is not globally routable (loopback, private ranges, link-local such
  as cloud metadata, multicast), and connects to the exact address it validated. The URL keeps
  its real hostname, so SNI and certificate verification are untouched; only the socket's
  destination is pinned. A DNS answer cannot change between the check and the connect.
- `get_capped()` follows redirects by hand so every hop goes through the same client, and
  reads bodies through a streamed cap instead of buffering an unknown size first.
"""

from __future__ import annotations

import ipaddress
import socket
import typing
from urllib.parse import urljoin, urlparse

import httpcore
import httpx

MAX_BODY_BYTES = 8 * 1024 * 1024
MAX_REDIRECTS = 5
_BLOCKED_SUFFIXES = (".local", ".internal", ".localhost")


class NotPublicHost(httpcore.ConnectError):
    """Raised by the pinning backend when a host does not resolve to a public address."""


def _is_global(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global and not ip.is_multicast


def public_address(host: str, port: int) -> str | None:
    """Resolve `host` and return one address to connect to, or None if any answer is not public."""
    if host == "localhost" or host.endswith(_BLOCKED_SUFFIXES):
        return None
    try:
        addresses = [ipaddress.ip_address(host.strip("[]"))]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        except (socket.gaierror, UnicodeError):
            return None
        addresses = [ipaddress.ip_address(info[4][0]) for info in infos]
    if not addresses or not all(_is_global(ip) for ip in addresses):
        return None
    return str(addresses[0])


def is_public_url(url: str) -> bool:
    """Cheap pre-check for a URL: http(s), a host, and that host resolving to public addresses."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        return False
    try:
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
    except ValueError:
        return False
    return public_address(parsed.hostname, port) is not None


class PinningBackend(httpcore.SyncBackend):
    """TCP connects go to an address this process resolved and validated, never to what the
    operating system would resolve a moment later."""

    def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: typing.Iterable[typing.Any] | None = None,
    ) -> httpcore.NetworkStream:
        address = public_address(host, port)
        if address is None:
            raise NotPublicHost(f"{host} does not resolve to a public address")
        return super().connect_tcp(address, port, timeout, local_address, socket_options)


class PinningTransport(httpx.HTTPTransport):
    """httpx transport on the pinning backend. TLS still verifies against the URL's hostname."""

    def __init__(self, **kwargs: typing.Any) -> None:
        super().__init__(**kwargs)
        self._pool = httpcore.ConnectionPool(
            ssl_context=httpx.create_ssl_context(verify=kwargs.get("verify", True)),
            max_connections=kwargs.get("limits", httpx.Limits()).max_connections,
            max_keepalive_connections=kwargs.get(
                "limits", httpx.Limits()
            ).max_keepalive_connections,
            keepalive_expiry=kwargs.get("limits", httpx.Limits()).keepalive_expiry,
            http1=True,
            http2=False,
            retries=kwargs.get("retries", 0),
            network_backend=PinningBackend(),
        )


def public_client(timeout: float = 15.0, headers: dict[str, str] | None = None) -> httpx.Client:
    """An httpx client that can only reach public hosts. Redirects are not followed automatically;
    use `get_capped`, which validates each hop."""
    return httpx.Client(
        transport=PinningTransport(),
        timeout=timeout,
        headers=headers,
        follow_redirects=False,
        trust_env=False,
    )


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
) -> tuple[httpx.Response, bytes | None, str] | None:
    """GET a public URL with a body cap: (response, body, final_url), or None when blocked.

    Every hop is pre-checked with `is_public_url` and, with a `public_client`, pinned again at
    connect time. `final_url` is the URL after redirects, for resolving relative links.
    """
    current = url
    for _ in range(MAX_REDIRECTS + 1):
        if not is_public_url(current):
            return None
        with client.stream("GET", current, headers=headers, follow_redirects=False) as response:
            location = response.headers.get("location")
            if response.is_redirect and location:
                current = urljoin(current, location)
                continue
            body = read_capped(response, limit)
        return response, body, current
    return None
