"""Felles datakatalog (data.norge.no), Digdir's national catalogue of public-sector data services.

Two public interfaces are combined:

- The search API gives the list: title, description, publisher name and org path, access rights,
  formats, ids. 100 hits a page, about a dozen pages for the whole catalogue.
- The SPARQL endpoint gives the fields the search hits leave out: endpoint URLs, endpoint
  descriptions (often an OpenAPI document), documentation pages, licences, keywords, status.
  One small query per predicate is faster and more robust than one wide query with OPTIONALs.

Both are joined on the data service URI. Raw responses are written to disk so a build can be
reproduced without the network.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from norapi.harvest import geonorge
from norapi.model import (
    ApiEntry,
    Provider,
    infer_auth,
    looks_like_spec,
    make_summary,
    normalise_format,
    slugify,
    stable_suffix,
)

log = logging.getLogger(__name__)

SEARCH_URL = "https://search.api.fellesdatakatalog.digdir.no/search/data-services"
SPARQL_URL = "https://sparql.fellesdatakatalog.digdir.no/"
USER_AGENT = "norapi/0.1 (+https://github.com/r33hAB/norapi)"

PREDICATES: dict[str, str] = {
    "endpoints": "http://www.w3.org/ns/dcat#endpointURL",
    "endpoint_descriptions": "http://www.w3.org/ns/dcat#endpointDescription",
    "pages": "http://xmlns.com/foaf/0.1/page",
    "landing_pages": "http://www.w3.org/ns/dcat#landingPage",
    "licenses": "http://purl.org/dc/terms/license",
    "formats": "http://purl.org/dc/terms/format",
    "media_types": "http://www.w3.org/ns/dcat#mediaType",
    "keywords": "http://www.w3.org/ns/dcat#keyword",
    "status": "http://www.w3.org/ns/adms#status",
    "versions": "http://www.w3.org/ns/dcat#version",
}

_ACCESS = {
    "PUBLIC": "open",
    "RESTRICTED": "restricted",
    "NON_PUBLIC": "non-public",
    "NON-PUBLIC": "non-public",
}
_STRICTEST_FIRST = ("non-public", "restricted", "open")

# Most services carry no access rights of their own; the datasets they serve often do.
DATASET_ACCESS_QUERY = (
    "SELECT ?s ?o WHERE { ?s a <http://www.w3.org/ns/dcat#DataService> ; "
    "<http://www.w3.org/ns/dcat#servesDataset> ?ds . "
    "?ds <http://purl.org/dc/terms/accessRights> ?o }"
)
_SECTOR_BY_ORGPATH = {"STAT": "stat", "KOMMUNE": "kommune", "FYLKE": "fylke", "PRIVAT": "privat"}


class FdkClient:
    def __init__(self, client: httpx.Client | None = None, page_size: int = 100) -> None:
        self.page_size = page_size
        self._http = client or httpx.Client(timeout=120, headers={"User-Agent": USER_AGENT})

    def search_pages(self) -> Iterator[list[dict[str, Any]]]:
        page = 0
        while True:
            body = {"query": "", "pagination": {"size": self.page_size, "page": page}}
            response = self._http.post(SEARCH_URL, json=body)
            response.raise_for_status()
            data = response.json()
            hits = data.get("hits") or []
            log.info("fdk: search page %d, %d hits", page, len(hits))
            if not hits:
                return
            yield hits
            paging = data.get("page") or {}
            page += 1
            if page >= int(paging.get("totalPages") or 0):
                return

    def sparql_pairs(self, predicate: str) -> list[tuple[str, str]]:
        return self.sparql_select(
            "SELECT ?s ?o WHERE { ?s a <http://www.w3.org/ns/dcat#DataService> ; "
            f"<{predicate}> ?o }}"
        )

    def sparql_select(self, query: str) -> list[tuple[str, str]]:
        """Run a SELECT that binds ?s and ?o."""
        response = self._http.get(
            SPARQL_URL,
            params={"query": query},
            headers={"Accept": "application/sparql-results+json"},
        )
        response.raise_for_status()
        bindings = response.json()["results"]["bindings"]
        return [(b["s"]["value"], b["o"]["value"]) for b in bindings]


def harvest(client: FdkClient, raw_dir: Path) -> dict[str, Any]:
    """Pull everything and write it under raw_dir. Returns the raw snapshot."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    hits: list[dict[str, Any]] = []
    for page in client.search_pages():
        hits.extend(page)
    extras: dict[str, list[tuple[str, str]]] = {}
    for name, predicate in PREDICATES.items():
        extras[name] = client.sparql_pairs(predicate)
        log.info("fdk: %s -> %d values", name, len(extras[name]))
    extras["dataset_access"] = client.sparql_select(DATASET_ACCESS_QUERY)
    log.info("fdk: dataset_access -> %d values", len(extras["dataset_access"]))
    snapshot = {
        "harvested_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "hits": hits,
        "extras": extras,
    }
    (raw_dir / "fdk.json").write_text(json.dumps(snapshot, ensure_ascii=False), encoding="utf-8")
    return snapshot


def load_snapshot(raw_dir: Path) -> dict[str, Any]:
    return json.loads((raw_dir / "fdk.json").read_text(encoding="utf-8"))


def geonorge_uuids(snapshot: dict[str, Any]) -> list[str]:
    """Kartkatalog ids for the services whose own access rights are blank."""
    blank = {
        h.get("uri") for h in snapshot["hits"] if not (h.get("accessRights") or {}).get("code")
    }
    found: set[str] = set()
    for name in ("pages", "landing_pages", "endpoint_descriptions"):
        for subject, url in snapshot["extras"].get(name, []):
            if subject in blank and (uuid := geonorge.uuid_in(url)):
                found.add(uuid)
    return sorted(found)


def to_entries(
    snapshot: dict[str, Any], geonorge_records: dict[str, dict[str, Any]] | None = None
) -> list[ApiEntry]:
    """Normalise the raw snapshot into registry entries, one per data service. Kartkatalog
    records (from geonorge.harvest) fill in access rights the catalogue leaves blank."""
    by_uri: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for name, pairs in snapshot["extras"].items():
        for subject, value in pairs:
            if value not in by_uri[subject][name]:
                by_uri[subject][name].append(value)

    harvested_at = snapshot.get("harvested_at")
    entries: list[ApiEntry] = []
    seen_ids: set[str] = set()
    seen_uris: set[str] = set()
    for hit in sorted(snapshot["hits"], key=lambda h: h.get("uri") or ""):
        uri = hit.get("uri")
        if not uri or uri in seen_uris:
            # the search API can return one data service on two pages; the URI identifies it
            continue
        seen_uris.add(uri)
        extra = by_uri.get(uri, {})
        entry = _hit_to_entry(hit, extra, harvested_at, geonorge_records or {})
        if entry.id in seen_ids:
            entry.id = f"{entry.id}-{stable_suffix(uri)}"
        seen_ids.add(entry.id)
        entries.append(entry)
    return entries


def _text(value: Any, *langs: str) -> str | None:
    """FDK strings are language maps: {'nb': ..., 'en': ...}."""
    if isinstance(value, str):
        return value.strip() or None
    if not isinstance(value, dict):
        return None
    for lang in langs or ("nb", "no", "nn", "en"):
        text = value.get(lang)
        if text and str(text).strip():
            return str(text).strip()
    for text in value.values():
        if text and str(text).strip():
            return str(text).strip()
    return None


def _resolve_access(
    hit: dict[str, Any], extra: dict[str, list[str]], geonorge_records: dict[str, dict[str, Any]]
) -> tuple[str, str | None]:
    """The service's own access rights, else Geonorge's record for it, else the strictest of the
    datasets it serves. When Geonorge and the datasets disagree, the strictest value wins: calling
    a restricted service open misleads more than the reverse. Returns the value and its source."""
    own = _ACCESS.get((hit.get("accessRights") or {}).get("code") or "")
    if own:
        return own, "fdk"
    from_geonorge = next(
        (
            found
            for name in ("pages", "landing_pages", "endpoint_descriptions")
            for url in extra.get(name, [])
            if (found := geonorge.access_of(geonorge_records.get(geonorge.uuid_in(url) or "")))
        ),
        None,
    )
    served = {_ACCESS.get(uri.rsplit("/", 1)[-1]) for uri in extra.get("dataset_access", [])}
    served.discard(None)
    if from_geonorge and served and from_geonorge not in served:
        candidates, source = served | {from_geonorge}, "conflict"
    elif from_geonorge:
        return from_geonorge, "geonorge"
    else:
        candidates, source = served, "fdk-dataset"
    for level in _STRICTEST_FIRST:
        if level in candidates:
            return level, source
    return "unknown", None


def _hit_to_entry(
    hit: dict[str, Any],
    extra: dict[str, list[str]],
    harvested_at: str | None,
    geonorge_records: dict[str, dict[str, Any]],
) -> ApiEntry:
    organization = hit.get("organization") or (hit.get("catalog") or {}).get("publisher") or {}
    org_path = organization.get("orgPath") or ""
    sector = next(
        (s for key, s in _SECTOR_BY_ORGPATH.items() if org_path.startswith(f"/{key}")), None
    )
    provider = Provider(
        name=organization.get("name") or _text(organization.get("prefLabel")) or "Ukjent",
        orgnr=organization.get("id"),
        org_path=org_path or None,
        sector=sector,
    )

    title = _text(hit.get("title")) or "Uten tittel"
    description = _text(hit.get("description"))
    access, access_from = _resolve_access(hit, extra, geonorge_records)

    descriptions = extra.get("endpoint_descriptions", [])
    spec_url = next((u for u in descriptions if looks_like_spec(u)), None)
    docs_candidates = extra.get("pages", []) + extra.get("landing_pages", [])
    docs_candidates += [u for u in descriptions if u != spec_url]
    docs_url = next((u for u in docs_candidates if u.startswith("http")), None)

    formats: list[str] = []
    raw_formats = list(hit.get("fdkFormatPrefixed") or []) + extra.get("formats", [])
    raw_formats += extra.get("media_types", [])
    for raw in raw_formats:
        normalised = normalise_format(raw)
        if normalised and normalised not in formats:
            formats.append(normalised)

    endpoints = [u for u in extra.get("endpoints", []) if u.startswith("http")]
    return ApiEntry(
        id=f"{slugify(provider.name, 30)}-{slugify(title, 50)}",
        title=title,
        title_en=_text(hit.get("title"), "en") if isinstance(hit.get("title"), dict) else None,
        provider=provider,
        description=description,
        summary=make_summary(description, title),
        access=access,
        auth=infer_auth(description, title),
        formats=formats,
        endpoints=endpoints,
        spec_url=spec_url,
        docs_url=docs_url,
        license=(extra.get("licenses") or [None])[0],
        keywords=extra.get("keywords", []),
        status=(extra.get("status") or [None])[0],
        modified=(hit.get("metadata") or {}).get("modified"),
        source={
            "kind": "fdk",
            "uri": hit.get("uri"),
            "catalogue_url": f"https://data.norge.no/data-services/{hit.get('id')}",
            "harvested_at": harvested_at,
            **({"access_from": access_from} if access_from else {}),
        },
    )
