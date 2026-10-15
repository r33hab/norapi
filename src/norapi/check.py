"""Link checks: does the documentation page, the spec and the first endpoint still answer?

Results are stored on each entry under `checks` so the registry can say which APIs were
reachable when it was built. A non-2xx is recorded, never treated as proof the API is gone:
many endpoints answer 401 or 405 to an anonymous GET and work fine with proper calls.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import httpx

from norapi.model import ApiEntry
from norapi.netguard import get_capped

log = logging.getLogger(__name__)
USER_AGENT = "norapi-linkcheck/0.1 (+https://github.com/r33hAB/norapi)"


def check_entries(entries: list[ApiEntry], timeout: float = 15.0, limit: int | None = None) -> int:
    checked = 0
    with httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}) as client:
        for entry in entries:
            if limit is not None and checked >= limit:
                break
            targets = {
                "docs_url": entry.docs_url,
                "spec_url": entry.spec_url,
                "endpoint": entry.probe_url or (entry.endpoints[0] if entry.endpoints else None),
            }
            results: dict[str, Any] = {}
            for name, url in targets.items():
                if not url:
                    continue
                results[name] = _probe(client, url)
            entry.checks = {
                "checked_at": datetime.now(UTC).isoformat(timespec="seconds"),
                **results,
            }
            checked += 1
            log.info("%s: %s", entry.id, {k: v.get("status") for k, v in results.items()})
    return checked


def verdict(status: int | None) -> str:
    """ok: content came back. answers: the server is there but wants parameters or credentials.
    missing: nothing there, gone, or the server failed."""
    if status is None:
        return "missing"
    if 200 <= status < 400:
        return "ok"
    if status in (400, 401, 403, 405, 406, 415, 422, 429):
        return "answers"
    return "missing"


def _probe(client: httpx.Client, url: str) -> dict[str, Any]:
    try:
        fetched = get_capped(client, url, limit=256 * 1024)
    except httpx.HTTPError as exc:
        return {"url": url, "status": None, "verdict": "missing", "error": type(exc).__name__}
    if fetched is None:
        return {
            "url": url,
            "status": None,
            "verdict": "missing",
            "error": "not a public http(s) URL, or a redirect into one",
        }
    response, _, final_url = fetched
    status = response.status_code
    return {"url": url, "status": status, "verdict": verdict(status), "final_url": final_url}
