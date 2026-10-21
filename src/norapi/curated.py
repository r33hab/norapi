"""Hand-written entries in registry/curated/*.yaml, and how they merge with harvested ones.

A curated file describes one provider and its APIs. Curated fields win over harvested fields
for the same API, harvested fields fill what the curated entry leaves out, and an entry that
matches nothing harvested stands on its own. Matching is explicit (`merge_with` is the FDK
data service URI) or by an identical endpoint URL.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from norapi.model import ACCESS_VALUES, AUTH_VALUES, ApiEntry, Provider, make_summary

_LIST_FIELDS = ("formats", "endpoints", "keywords", "tags", "caveats")


def load_access_review(path: Path) -> dict[str, dict[str, Any]]:
    """registry/access-review.yaml: access set by a manual check for harvested entries the
    catalogues leave blank, keyed by catalogue URI."""
    if not path.exists():
        return {}
    document = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    checked = str(document.get("checked") or "")
    review: dict[str, dict[str, Any]] = {}
    for item in document.get("entries") or []:
        if item["access"] not in ACCESS_VALUES or item.get("auth", "unknown") not in AUTH_VALUES:
            raise ValueError(f"{path.name}: {item.get('id')}: unknown access or auth value")
        review[item["uri"]] = {**item, "checked": checked}
    return review


def apply_access_review(harvested: list[ApiEntry], review: dict[str, dict[str, Any]]) -> None:
    """Fill access the catalogues leave blank. Only a fallback: once Felles datakatalog,
    Geonorge or the served datasets give a value, that value wins and the review is ignored."""
    for entry in harvested:
        item = review.get(entry.source.get("uri") or "")
        if item is None or entry.access != "unknown":
            continue
        entry.access = item["access"]
        if item.get("auth") and entry.auth == "unknown":
            entry.auth = item["auth"]
        entry.caveats = [*entry.caveats, *(item.get("caveats") or [])]
        entry.source["access_from"] = "review"
        entry.source["access_note"] = item["reason"]
        entry.source["access_checked"] = item["checked"]


def load_curated(curated_dir: Path) -> list[ApiEntry]:
    entries: list[ApiEntry] = []
    for file in sorted(curated_dir.glob("*.yaml")):
        document = yaml.safe_load(file.read_text(encoding="utf-8")) or {}
        provider = Provider(**document["provider"])
        for raw in document.get("apis") or []:
            raw = dict(raw)
            merge_with = raw.pop("merge_with", None)
            raw.setdefault("summary", make_summary(raw.get("description"), raw["title"]))
            raw["source"] = {
                "kind": "curated",
                "file": file.name,
                "merge_with": merge_with,
                "updated": str(document.get("updated") or ""),
            }
            entries.append(ApiEntry(provider=provider, **raw))
    return entries


def merge(curated: list[ApiEntry], harvested: list[ApiEntry]) -> list[ApiEntry]:
    """Curated entries override matching harvested ones; everything else passes through."""
    by_uri = {e.source.get("uri"): e for e in harvested if e.source.get("uri")}
    by_endpoint: dict[str, ApiEntry] = {}
    for entry in harvested:
        for url in entry.endpoints:
            by_endpoint.setdefault(url.rstrip("/"), entry)

    consumed: set[int] = set()
    merged: list[ApiEntry] = []
    for entry in curated:
        match = by_uri.get(entry.source.get("merge_with"))
        if match is None:
            match = next(
                (
                    by_endpoint[u.rstrip("/")]
                    for u in entry.endpoints
                    if u.rstrip("/") in by_endpoint
                ),
                None,
            )
        if match is None:
            merged.append(entry)
            continue
        consumed.add(id(match))
        merged.append(_overlay(entry, match))

    merged.extend(e for e in harvested if id(e) not in consumed)
    return merged


def _overlay(curated: ApiEntry, harvested: ApiEntry) -> ApiEntry:
    data: dict[str, Any] = harvested.to_dict()
    override = curated.to_dict()
    for key, value in override.items():
        if key == "source":
            continue
        if key in _LIST_FIELDS:
            combined = list(value) + [v for v in data.get(key) or [] if v not in value]
            data[key] = combined
        elif key == "provider":
            data[key] = {**data.get("provider", {}), **{k: v for k, v in value.items() if v}}
        elif value not in (None, "", "unknown"):
            data[key] = value
    data["source"] = {
        "kind": "curated+fdk",
        "file": curated.source.get("file"),
        "uri": harvested.source.get("uri"),
        "catalogue_url": harvested.source.get("catalogue_url"),
        "harvested_at": harvested.source.get("harvested_at"),
    }
    return ApiEntry.from_dict(data)
