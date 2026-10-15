"""Build the distributable registry: registry.json, llms.txt, and the FTS5 search index."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from norapi import __version__
from norapi.model import CATEGORIES, ApiEntry

REGISTRY_DIR = Path(__file__).resolve().parents[2] / "registry"
REGISTRY_JSON = REGISTRY_DIR / "registry.json"
LLMS_TXT = REGISTRY_DIR / "llms.txt"
INDEX_DB = REGISTRY_DIR / ".index.sqlite"


def write_registry(entries: list[ApiEntry], registry_json: Path = REGISTRY_JSON) -> dict[str, Any]:
    entries = sorted(
        entries, key=lambda e: (e.source.get("kind") != "curated", e.provider.name, e.title)
    )
    kinds: dict[str, int] = {}
    for entry in entries:
        kinds[entry.source.get("kind", "?")] = kinds.get(entry.source.get("kind", "?"), 0) + 1
    document = {
        "name": "norapi",
        "version": __version__,
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "count": len(entries),
        "sources": kinds,
        "categories": CATEGORIES,
        "apis": [e.to_dict() for e in entries],
    }
    registry_json.parent.mkdir(parents=True, exist_ok=True)
    registry_json.write_text(json.dumps(document, ensure_ascii=False, indent=1), encoding="utf-8")
    write_llms_txt(entries, registry_json.with_name("llms.txt"))
    build_index(registry_json, registry_json.with_name(".index.sqlite"))
    return document


def write_llms_txt(entries: list[ApiEntry], path: Path) -> None:
    """A compact Markdown listing a language model can read in one go (curated APIs first)."""
    lines = [
        "# Norske offentlige API-er (norapi)",
        "",
        "> Registry of Norwegian public APIs. One line per API: title, provider, access, formats, "
        "then docs and endpoint. Full data in registry.json. Source and licence per API apply.",
        "",
    ]
    curated = [e for e in entries if e.source.get("kind", "").startswith("curated")]
    harvested = [e for e in entries if e not in curated]
    lines.append("## Curated")
    lines.append("")
    lines.extend(_llms_line(e) for e in curated)
    lines.append("")
    lines.append(f"## Harvested from Felles datakatalog ({len(harvested)})")
    lines.append("")
    lines.extend(_llms_line(e) for e in harvested)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _llms_line(entry: ApiEntry) -> str:
    parts = [f"- **{entry.title}** ({entry.provider.name}; {entry.access}"]
    if entry.auth != "unknown":
        parts[0] += f", auth: {entry.auth}"
    if entry.formats:
        parts[0] += f"; {', '.join(entry.formats[:4])}"
    parts[0] += f"): {entry.summary or ''}"
    links = []
    if entry.docs_url:
        links.append(f"docs {entry.docs_url}")
    if entry.spec_url:
        links.append(f"spec {entry.spec_url}")
    if entry.endpoints:
        links.append(f"endpoint {entry.endpoints[0]}")
    if links:
        parts.append(" " + " | ".join(links))
    return "".join(parts)


def build_index(registry_json: Path = REGISTRY_JSON, index_db: Path = INDEX_DB) -> Path:
    """Create the SQLite FTS5 index from registry.json. About a second for a thousand rows."""
    document = json.loads(registry_json.read_text(encoding="utf-8"))
    tmp = index_db.with_suffix(".tmp")
    if tmp.exists():
        tmp.unlink()
    con = sqlite3.connect(tmp)
    try:
        con.executescript(
            """
            create table apis (
                id text primary key, title text, provider text, access text, auth text,
                category text, formats text, kind text, json text not null
            );
            create virtual table api_fts using fts5(
                id unindexed, title, summary, description, provider, keywords, category,
                formats, endpoints, tags,
                tokenize = 'unicode61 remove_diacritics 2'
            );
            create table meta (key text primary key, value text);
            """
        )
        for api in document["apis"]:
            con.execute(
                "insert into apis values (?,?,?,?,?,?,?,?,?)",
                (
                    api["id"],
                    api["title"],
                    api["provider"]["name"],
                    api["access"],
                    api["auth"],
                    api.get("category"),
                    " ".join(api.get("formats") or []),
                    api.get("source", {}).get("kind"),
                    json.dumps(api, ensure_ascii=False),
                ),
            )
            con.execute(
                "insert into api_fts values (?,?,?,?,?,?,?,?,?,?)",
                (
                    api["id"],
                    " ".join(filter(None, [api["title"], api.get("title_en")])),
                    api.get("summary") or "",
                    api.get("description") or "",
                    api["provider"]["name"],
                    " ".join(api.get("keywords") or []),
                    CATEGORIES.get(api.get("category") or "", ""),
                    " ".join(api.get("formats") or []),
                    " ".join(api.get("endpoints") or []),
                    " ".join(api.get("tags") or []),
                ),
            )
        con.execute("insert into meta values ('generated_at', ?)", (document["generated_at"],))
        con.execute("insert into meta values ('count', ?)", (str(document["count"]),))
        con.commit()
    finally:
        con.close()
    tmp.replace(index_db)
    return index_db


def ensure_index(registry_json: Path = REGISTRY_JSON, index_db: Path = INDEX_DB) -> Path:
    """Rebuild the index when it is missing or older than registry.json."""
    if not registry_json.exists():
        raise FileNotFoundError(f"{registry_json} does not exist; run `norapi build` first")
    if not index_db.exists() or index_db.stat().st_mtime < registry_json.stat().st_mtime:
        build_index(registry_json, index_db)
    return index_db
