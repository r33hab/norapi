"""Find out, by calling it, whether a harvested API answers without credentials.

Felles datakatalog has no auth field, so most harvested entries say `auth: unknown`. One
anonymous request settles the common case: a WMS that returns its capabilities, a REST endpoint
that returns JSON, an ArcGIS server that returns its service description. Those are recorded as
`auth: none` in registry/auth-review.yaml, keyed by catalogue URI, with what was observed.

Only a positive answer sets anything. A 401, a login page or a timeout proves little about
*which* credentials an API wants, so those keep `auth: unknown`; the observation is still
written down so the next run and a human reviewer can see why.
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

import httpx
import yaml

from norapi.model import AUTH_VALUES, ApiEntry
from norapi.netguard import get_capped, public_client

log = logging.getLogger(__name__)
USER_AGENT = "norapi-authprobe/0.1 (+https://github.com/r33hab/norapi)"
_OGC = ("WMS", "WFS", "WMTS", "WCS")
_MAX_BODY = 2 * 1024 * 1024
_HEADER = (
    "# Auth for harvested entries, from one anonymous call (`norapi probe-auth`).\n"
    "# Felles datakatalog has no auth field. `none` means the call returned the service's own\n"
    "# content without credentials; every other result keeps `unknown` and says what was seen.\n"
    "# Applied only while the entry's auth is still unknown; matching is on the catalogue URI.\n"
)


def probe_request(entry: ApiEntry) -> str | None:
    """The URL to call: the probe URL or first endpoint, made to ask for a machine answer
    (GetCapabilities for an OGC service, `f=json` for an ArcGIS REST service)."""
    url = entry.probe_url or (entry.endpoints[0] if entry.endpoints else None)
    if not url or not url.startswith("http"):
        return None
    parsed = urlparse(url)
    query = {k.lower(): v for k, v in parse_qs(parsed.query, keep_blank_values=True).items()}
    service = _ogc_service(entry, url)
    extra: dict[str, str] = {}
    if service and "request" not in query:
        extra = {"service": service, "request": "GetCapabilities"}
        if "service" in query:
            extra.pop("service")
    elif "/rest/services" in parsed.path.lower() and "f" not in query:
        extra = {"f": "json"}
    if not extra:
        return url
    joined = "&".join(filter(None, [parsed.query, urlencode(extra)]))
    return urlunparse(parsed._replace(query=joined))


def _ogc_service(entry: ApiEntry, url: str) -> str | None:
    lowered = url.lower()
    for service in _OGC:
        if f"service={service.lower()}" in lowered:
            return service
    path = urlparse(url).path.lower()
    for service in ("WMTS", "WMS", "WFS", "WCS"):  # WMTS before WMS: "wms" is in "wmts"
        if service.lower() in path:
            return service
    formats = {f.upper() for f in entry.formats}
    return next((s for s in _OGC if s in formats), None)


def classify(status: int | None, content_type: str, body: bytes | None) -> tuple[str, str]:
    """(auth, observation) for one anonymous answer."""
    if status is None:
        return "unknown", "no answer"
    if status in (401, 403, 407):
        return "unknown", f"anonymous call refused ({status})"
    if status >= 400:
        return "unknown", f"HTTP {status}"
    content_type = content_type.lower()
    if body is None:  # larger than the cap: the type is all there is to go on
        if "html" in content_type:
            return "unknown", f"HTTP {status}, an HTML page (docs or login), not the service"
        return "none", f"anonymous call returns a large {content_type or 'body'}"
    text = (body or b"")[:20000].decode("utf-8", errors="replace").lstrip()
    lowered = text[:4000].lower()
    if not text:
        return "unknown", f"HTTP {status}, empty body"
    if "html" in content_type or lowered.startswith(("<!doctype html", "<html")):
        return "unknown", f"HTTP {status}, an HTML page (docs or login), not the service"
    if lowered.startswith("<"):
        if "exceptionreport" in lowered or "serviceexception" in lowered:
            if any(w in lowered for w in ("auth", "token", "login", "forbidden", "denied")):
                return "unknown", "OGC exception about credentials"
            return "unknown", "OGC exception"
        if "capabilities" in lowered[:2000]:
            return "none", "GetCapabilities answers anonymously"
        return "none", "anonymous call returns XML"
    if lowered.startswith(("{", "[")):
        try:
            data = json.loads(body) if len(body) < 20000 else None
        except json.JSONDecodeError:
            data = None
        error = data.get("error") if isinstance(data, dict) else None
        if isinstance(error, dict):  # ArcGIS answers 200 with {"error": {"code": 499, ...}}
            message = str(error.get("message") or "").lower()
            code = error.get("code")
            if code in (401, 403, 498, 499) or "token" in message:
                return "unknown", f"anonymous call refused (error {code}: token required)"
            return "unknown", f"error in JSON body ({code})"
        return "none", "anonymous call returns JSON"
    if "csv" in content_type or "zip" in content_type or "octet-stream" in content_type:
        return "none", "anonymous call returns data"
    return "unknown", f"HTTP {status}, {content_type or 'unknown content'}"


def probe(client: httpx.Client, entry: ApiEntry) -> dict[str, Any]:
    url = probe_request(entry)
    base = {"id": entry.id, "uri": entry.source.get("uri")}
    if url is None:
        return {**base, "auth": "unknown", "observed": "no endpoint to call"}
    try:
        fetched = get_capped(client, url, limit=_MAX_BODY)
    except httpx.HTTPError as exc:
        observed = f"no answer ({type(exc).__name__})"
        return {**base, "auth": "unknown", "url": url, "observed": observed}
    if fetched is None:
        return {**base, "auth": "unknown", "url": url, "observed": "not a public URL"}
    response, body, _ = fetched
    auth, observed = classify(response.status_code, response.headers.get("content-type", ""), body)
    if auth == "none" and observed.startswith("GetCapabilities") and entry.access != "open":
        # Norge digitalt services publish capabilities openly and want a login for the data.
        auth, observed = "unknown", f"GetCapabilities answers, but access is {entry.access}"
    return {**base, "auth": auth, "url": url, "observed": observed}


def probe_entries(
    entries: list[ApiEntry], timeout: float = 15.0, workers: int = 8
) -> list[dict[str, Any]]:
    """Probe every harvested entry whose auth is still unknown."""
    targets = [
        e
        for e in entries
        if e.auth == "unknown" and e.source.get("uri") and e.source.get("kind") != "curated"
    ]
    log.info("probe-auth: %d entries with unknown auth", len(targets))
    with public_client(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(lambda e: probe(client, e), targets))
    return sorted(results, key=lambda r: r["id"])


def write_review(results: list[dict[str, Any]], path: Path, checked: date | None = None) -> None:
    document = {"checked": (checked or date.today()).isoformat(), "entries": results}
    body = yaml.safe_dump(document, allow_unicode=True, sort_keys=False, width=100)
    path.write_text(_HEADER + body, encoding="utf-8")


def load_review(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    checked = str(document.get("checked") or "")
    review: dict[str, dict[str, Any]] = {}
    for item in document.get("entries") or []:
        if item.get("auth", "unknown") not in AUTH_VALUES:
            raise ValueError(f"{path.name}: {item.get('id')}: unknown auth value")
        if item.get("uri"):
            review[item["uri"]] = {**item, "checked": checked}
    return review


def apply_review(entries: list[ApiEntry], review: dict[str, dict[str, Any]]) -> int:
    """Fill auth the catalogue leaves blank. Only a fallback: any other value wins."""
    applied = 0
    for entry in entries:
        item = review.get(entry.source.get("uri") or "")
        if item is None or entry.auth != "unknown" or item["auth"] == "unknown":
            continue
        entry.auth = item["auth"]
        entry.source["auth_from"] = "probe"
        entry.source["auth_note"] = item["observed"]
        entry.source["auth_checked"] = item["checked"]
        applied += 1
    return applied
