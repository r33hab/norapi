"""Geonorge's kartkatalog, the metadata catalogue behind most Norwegian map services.

Felles datakatalog leaves the access rights blank for most of the services it harvests from
Geonorge, while the kartkatalog record for the same service says whether it is open data,
restricted (Norge digitalt) or protected. One small GET per service; only the access fields are
kept, and they are written to disk next to the catalogue snapshot so a build can run offline.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

import httpx

log = logging.getLogger(__name__)

METADATA_URL = "https://kartkatalog.geonorge.no/api/getdata/{uuid}"
USER_AGENT = "norapi/0.1 (+https://github.com/r33hAB/norapi)"
SNAPSHOT = "geonorge.json"

_UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
_FIELDS = ("AccessIsOpendata", "AccessIsRestricted", "AccessIsProtected", "DataAccess")


def uuid_in(url: str) -> str | None:
    """The metadata id in a kartkatalog link, in any of its URL shapes."""
    if "kartkatalog.geonorge.no" not in url:
        return None
    match = _UUID.search(url.lower())
    return match.group(0) if match else None


def harvest(
    uuids: Iterable[str], raw_dir: Path, client: httpx.Client | None = None, workers: int = 8
) -> dict[str, dict[str, Any]]:
    """Fetch the access fields for each id and write them under raw_dir."""
    http = client or httpx.Client(timeout=60, headers={"User-Agent": USER_AGENT})

    def fetch(uuid: str) -> tuple[str, dict[str, Any] | None]:
        try:
            response = http.get(METADATA_URL.format(uuid=uuid))
            response.raise_for_status()
            data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            log.warning("geonorge: %s: %s", uuid, exc)
            return uuid, None
        return uuid, {key: data.get(key) for key in _FIELDS}

    with ThreadPoolExecutor(max_workers=workers) as pool:
        records = {uuid: rec for uuid, rec in pool.map(fetch, sorted(set(uuids))) if rec}
    raw_dir.mkdir(parents=True, exist_ok=True)
    (raw_dir / SNAPSHOT).write_text(
        json.dumps(records, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    return records


def load_snapshot(raw_dir: Path) -> dict[str, dict[str, Any]]:
    path = raw_dir / SNAPSHOT
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def access_of(record: dict[str, Any] | None) -> str | None:
    """Registry access value for a kartkatalog record; the strictest flag wins."""
    if not record:
        return None
    if record.get("AccessIsProtected"):
        return "non-public"
    if record.get("AccessIsRestricted"):
        return "restricted"
    if record.get("AccessIsOpendata"):
        return "open"
    return None
