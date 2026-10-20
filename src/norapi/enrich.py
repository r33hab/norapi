"""Fetch OpenAPI / Swagger documents and index their operations.

For every entry that points at a specification (`spec_url`, or a docs page that is a Swagger UI),
the document is fetched, parsed, and reduced to two things: a short summary stored on the entry
(`spec`) and one row per operation in `registry/operations.json`. A search can then land on
`GET /vegobjekter/{id}` instead of only on the API that owns it.

Resolution is forgiving, because catalogues rarely link the raw document:
- SwaggerHub UI links (`app.swaggerhub.com`) become API links (`api.swaggerhub.com`).
- A Swagger UI or ReDoc page is read for the document URL it loads.
- Failing that, the usual neighbours are tried (`openapi.json`, `v3/api-docs`, ...).

Raw documents are cached under data/specs/ so re-runs do not hit the network again.
"""

from __future__ import annotations

import json
import logging
import re
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
import yaml

from norapi.model import ApiEntry
from norapi.netguard import get_capped, public_client

log = logging.getLogger(__name__)

USER_AGENT = "norapi-enrich/0.1 (+https://github.com/r33hAB/norapi)"
MAX_BYTES = 8 * 1024 * 1024  # a specification larger than this is not worth indexing
METHODS = ("get", "post", "put", "patch", "delete", "head", "options")
NEIGHBOURS = (
    "openapi.json",
    "openapi.yaml",
    "swagger.json",
    "swagger.yaml",
    "v3/api-docs",
    "v2/api-docs",
    "api-docs",
    "swagger/v1/swagger.json",
    "openapi/v1.json",
)
_UI_HINTS = ("swagger", "redoc", "api-docs", "apidocs", "openapi")
_URL_IN_PAGE = re.compile(
    r"""(?:url|spec-url|specUrl)\s*[:=]\s*["']([^"']+\.(?:json|ya?ml)[^"']*|[^"']*api-docs[^"']*)["']""",
    re.IGNORECASE,
)
_INITIALIZER = re.compile(r"""["']([^"']*swagger-initializer\.js[^"']*)["']""")


class SpecFetcher:
    def __init__(self, client: httpx.Client | None = None, timeout: float = 15.0) -> None:
        self._http = client or public_client(
            timeout=timeout,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "application/json, application/yaml, text/yaml, text/plain, "
                "text/html;q=0.5, */*;q=0.1",
            },
        )

    def resolve(self, url: str, budget: int = 8) -> tuple[str, dict[str, Any]] | None:
        """Return (final_url, document) for the first OpenAPI document reachable from url."""
        tried: set[str] = set()
        queue = [normalise_url(url)]
        while queue and budget > 0:
            candidate = queue.pop(0)
            if candidate in tried:
                continue
            tried.add(candidate)
            budget -= 1
            try:
                fetched = get_capped(self._http, candidate, limit=MAX_BYTES)
            except httpx.HTTPError as exc:
                log.debug("%s: %s", candidate, type(exc).__name__)
                continue
            if fetched is None:
                log.debug("%s: not a public http(s) URL, skipped", candidate)
                continue
            response, body, final_url = fetched
            if response.status_code >= 400 or body is None:
                continue
            text = body.decode(response.encoding or "utf-8", errors="replace")
            document = parse_document(text, response.headers.get("content-type", ""))
            if document is not None and not is_sample(document, final_url):
                return final_url, document
            if document is not None:
                log.debug("%s: sample document, ignored", candidate)
                continue
            # Not a document: maybe a UI page that tells us where the document is. What the
            # page itself points at goes to the front of the queue; guessed neighbours last.
            discovered = [u for u in urls_from_page(text, final_url) if u not in tried]
            queue = discovered + queue
            if looks_like_ui(candidate):
                queue.extend(u for u in neighbour_urls(candidate) if u not in tried)
        return None


def normalise_url(url: str) -> str:
    parsed = urlparse(url)
    if parsed.netloc == "app.swaggerhub.com":
        return url.replace("app.swaggerhub.com", "api.swaggerhub.com", 1)
    return url


def looks_like_ui(url: str) -> bool:
    lowered = url.lower()
    return any(hint in lowered for hint in _UI_HINTS)


MAX_YAML_NODES = 2_000_000  # an 8 MB spec has far fewer; only alias or merge-key tricks reach this


def _load_yaml(text: str) -> Any:
    """safe_load, after checking how large the document becomes once aliases and `<<` merge keys
    are expanded. Composing keeps aliases shared and is linear in the input; constructing copies
    merged mappings, so nested merges in a few hundred bytes would otherwise exhaust memory
    inside the loader."""
    root = yaml.compose(text, Loader=yaml.SafeLoader)
    if root is None:
        return None
    if _expanded_nodes(root, {}, set()) > MAX_YAML_NODES:
        raise ValueError("specification expands past the node cap")
    return yaml.safe_load(text)


def _expanded_nodes(node: yaml.Node, memo: dict[int, int], active: set[int]) -> int:
    key = id(node)
    if key in memo:
        return memo[key]
    if key in active:
        raise ValueError("recursive YAML alias")
    if isinstance(node, yaml.ScalarNode):
        return 1
    active.add(key)
    if isinstance(node, yaml.MappingNode):
        children = [child for pair in node.value for child in pair]
    else:
        children = node.value
    total = 1 + sum(_expanded_nodes(child, memo, active) for child in children)
    active.discard(key)
    memo[key] = total
    return total


def _json_safe(document: Any) -> Any:
    """YAML turns unquoted dates into date objects and status codes into int keys; a JSON round
    trip makes the document match what a JSON spec would give. Aliases are shared on load but
    copied on encode, so a few kilobytes of nested aliases can expand to gigabytes: the encoded
    size is capped, and a self-referencing alias raises ValueError (circular reference)."""
    limit = 4 * MAX_BYTES
    chunks: list[str] = []
    size = 0
    for chunk in json.JSONEncoder(default=str, ensure_ascii=False).iterencode(document):
        size += len(chunk)
        if size > limit:
            raise ValueError("specification expands past the size cap")
        chunks.append(chunk)
    return json.loads("".join(chunks))


def parse_document(text: str, content_type: str) -> dict[str, Any] | None:
    stripped = text.lstrip()
    if not stripped:
        return None
    document: Any = None
    if stripped.startswith("<"):
        return None
    if stripped.startswith("{") or "json" in content_type:
        try:
            document = json.loads(stripped)
        except json.JSONDecodeError:
            if stripped.startswith("{"):
                return None
            # some servers label a YAML document application/json (Vegvesen's parking register)
    if document is None and ("openapi:" in stripped[:4000] or "swagger:" in stripped[:4000]):
        try:
            document = _json_safe(_load_yaml(stripped))
        except (yaml.YAMLError, ValueError, RecursionError, TypeError):
            # TypeError: a mapping key JSON cannot hold, such as an unquoted date
            return None
    if not isinstance(document, dict) or not isinstance(document.get("paths"), dict):
        return None
    if "openapi" not in document and "swagger" not in document:
        return None
    return document


def is_sample(document: dict[str, Any], url: str) -> bool:
    """Swagger UI ships with the Petstore example; a page that never changed it is not an API."""
    if "petstore" in url.lower():
        return True
    title = str((document.get("info") or {}).get("title") or "").lower()
    paths = document.get("paths") or {}
    return title.startswith("swagger petstore") or "/pet/{petId}" in paths or "/pet" in paths


def urls_from_page(html: str, page_url: str) -> list[str]:
    """Where a Swagger UI / ReDoc page loads its document from, best effort."""
    found: list[str] = []
    for match in _URL_IN_PAGE.finditer(html):
        if "petstore" not in match.group(1).lower():
            found.append(urljoin(page_url, match.group(1)))
    for match in _INITIALIZER.finditer(html):
        found.append(urljoin(page_url, match.group(1)))
    return found[:4]


def neighbour_urls(url: str) -> list[str]:
    parsed = urlparse(url)
    origin = f"{parsed.scheme}://{parsed.netloc}/"
    directory = url if url.endswith("/") else url.rsplit("/", 1)[0] + "/"
    candidates: list[str] = []
    for base in (directory, origin):
        for name in NEIGHBOURS:
            candidate = urljoin(base, name)
            if candidate not in candidates:
                candidates.append(candidate)
    return candidates


def summarise(document: dict[str, Any], source_url: str, fetched_at: str) -> dict[str, Any]:
    info = document.get("info") or {}
    servers = [s.get("url") for s in document.get("servers") or [] if isinstance(s, dict)]
    if not servers and document.get("host"):
        scheme = (document.get("schemes") or ["https"])[0]
        servers = [f"{scheme}://{document['host']}{document.get('basePath') or ''}"]
    version = document.get("openapi") or document.get("swagger")
    tags = sorted({t for op in operations(document, "x") for t in op["tags"]})
    return {
        "format": f"{'openapi' if 'openapi' in document else 'swagger'} {version}",
        "title": info.get("title"),
        "version": str(info.get("version") or "") or None,
        "servers": [s for s in servers if s][:5],
        "operations": sum(1 for _ in operations(document, "x")),
        "tags": tags[:40],
        "source_url": source_url,
        "fetched_at": fetched_at,
    }


def operations(document: dict[str, Any], api_id: str) -> Iterable[dict[str, Any]]:
    for path, item in (document.get("paths") or {}).items():
        if not isinstance(item, dict):
            continue
        for method in METHODS:
            op = item.get(method)
            if not isinstance(op, dict):
                continue
            description = re.sub(r"\s+", " ", str(op.get("description") or "")).strip()
            yield {
                "api_id": api_id,
                "method": method.upper(),
                "path": str(path),
                "summary": (op.get("summary") or "").strip() or None,
                "description": description[:240] or None,
                "tags": [str(t) for t in op.get("tags") or []],
                "operation_id": op.get("operationId"),
                "deprecated": bool(op.get("deprecated")),
            }


def candidate_urls(entry: ApiEntry) -> list[str]:
    urls: list[str] = []
    if entry.spec_url:
        urls.append(entry.spec_url)
    if entry.docs_url and looks_like_ui(entry.docs_url) and entry.docs_url not in urls:
        urls.append(entry.docs_url)
    return urls


def enrich_entries(
    entries: list[ApiEntry],
    cache_dir: Path,
    fetcher: SpecFetcher | None = None,
    workers: int = 8,
    limit: int | None = None,
    refresh: bool = False,
    max_age: timedelta = timedelta(days=30),
) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
    """Resolve specs for every entry that points at one. Returns (summaries by id, operations)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    fetcher = fetcher or SpecFetcher()
    targets = [e for e in entries if candidate_urls(e)]
    if limit is not None:
        targets = targets[:limit]
    log.info("enrich: %d entries point at a specification", len(targets))

    def work(entry: ApiEntry) -> tuple[str, dict[str, Any] | None]:
        cache_file = cache_dir / f"{entry.id}.json"
        if cache_file.exists() and not refresh:
            cached = json.loads(cache_file.read_text(encoding="utf-8"))
            fetched = datetime.fromisoformat(cached["fetched_at"])
            if datetime.now(UTC) - fetched < max_age:
                return entry.id, cached
        resolved = None
        for url in candidate_urls(entry):
            resolved = fetcher.resolve(url)
            if resolved:
                break
        record: dict[str, Any] = {"fetched_at": datetime.now(UTC).isoformat(timespec="seconds")}
        if resolved:
            record["source_url"], record["document"] = resolved
        else:
            record["document"] = None
        cache_file.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
        return entry.id, record

    summaries: dict[str, dict[str, Any]] = {}
    ops: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for api_id, record in pool.map(work, targets):
            document = (record or {}).get("document")
            if not document:
                continue
            summaries[api_id] = summarise(document, record["source_url"], record["fetched_at"])
            ops.extend(operations(document, api_id))
            log.info(
                "%s: %d operations (%s)",
                api_id,
                summaries[api_id]["operations"],
                record["source_url"],
            )
    return summaries, ops


def write_enrichment(
    summaries: dict[str, dict[str, Any]], ops: list[dict[str, Any]], registry_dir: Path
) -> None:
    now = datetime.now(UTC).isoformat(timespec="seconds")
    (registry_dir / "specs.json").write_text(
        json.dumps(
            {"generated_at": now, "count": len(summaries), "specs": summaries},
            ensure_ascii=False,
            indent=1,
        ),
        encoding="utf-8",
    )
    (registry_dir / "operations.json").write_text(
        json.dumps(
            {"generated_at": now, "count": len(ops), "operations": ops},
            ensure_ascii=False,
            indent=0,
        ),
        encoding="utf-8",
    )


def load_specs(registry_dir: Path) -> dict[str, dict[str, Any]]:
    file = registry_dir / "specs.json"
    if not file.exists():
        return {}
    return json.loads(file.read_text(encoding="utf-8")).get("specs", {})


def load_operations(registry_dir: Path) -> list[dict[str, Any]]:
    file = registry_dir / "operations.json"
    if not file.exists():
        return []
    return json.loads(file.read_text(encoding="utf-8")).get("operations", [])
