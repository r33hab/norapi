"""Query the FTS5 index. Used by the CLI, the MCP server and the site generator alike."""

from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Any

from norapi.build import INDEX_DB, REGISTRY_JSON, ensure_index
from norapi.model import CATEGORIES

_TOKEN = re.compile(r"[\wæøåÆØÅ\-\.{}/]+", re.UNICODE)


def fts_query(text: str) -> str:
    """Turn free text into an FTS5 query: every term quoted, prefix-matched, all required."""
    terms = [t.strip("-./{}") for t in _TOKEN.findall(text or "")]
    terms = [t for t in terms if t]
    if not terms:
        return ""
    return " ".join(f'"{t}"*' if len(t) >= 3 else f'"{t}"' for t in terms)


class Registry:
    def __init__(self, index_db: Path) -> None:
        self._con = sqlite3.connect(f"file:{index_db}?mode=ro", uri=True)
        self._con.row_factory = sqlite3.Row

    @classmethod
    def open(cls, registry_json: Path = REGISTRY_JSON, index_db: Path = INDEX_DB) -> Registry:
        return cls(ensure_index(registry_json, index_db))

    def close(self) -> None:
        self._con.close()

    def search(
        self,
        query: str,
        limit: int = 10,
        access: str | None = None,
        provider: str | None = None,
        fmt: str | None = None,
        category: str | None = None,
        auth: str | None = None,
    ) -> list[dict[str, Any]]:
        where = []
        params: list[Any] = []
        if access:
            where.append("a.access = ?")
            params.append(access)
        if auth:
            where.append("a.auth = ?")
            params.append(auth)
        if provider:
            where.append("lower(a.provider) like ?")
            params.append(f"%{provider.lower()}%")
        if fmt:
            where.append("lower(a.formats) like ?")
            params.append(f"%{fmt.lower()}%")
        if category:
            where.append("a.category = ?")
            params.append(category)
        filters = (" and " + " and ".join(where)) if where else ""

        match = fts_query(query)
        if match:
            sql = (
                "select a.json, "
                "bm25(api_fts, 0, 12.0, 6.0, 2.0, 4.0, 5.0, 2.0, 1.0, 1.0, 3.0) as rank "
                "from api_fts join apis a on a.id = api_fts.id "
                f"where api_fts match ?{filters} "
                "order by rank, a.kind = 'fdk', a.title limit ?"
            )
            rows = self._con.execute(sql, [match, *params, limit]).fetchall()
        else:
            sql = (
                f"select a.json, 0 as rank from apis a where 1=1{filters} "
                "order by a.kind = 'fdk', a.provider, a.title limit ?"
            )
            rows = self._con.execute(sql, [*params, limit]).fetchall()
        results = []
        for row in rows:
            api = json.loads(row["json"])
            api["_rank"] = round(float(row["rank"]), 3)
            results.append(api)
        return results

    def search_operations(
        self, query: str, limit: int = 20, api_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Operations (method + path + summary) from indexed OpenAPI documents."""
        match = fts_query(query)
        if not match:
            return []
        params: list[Any] = [match]
        filters = ""
        if api_id:
            filters = " and api_id = ?"
            params.append(api_id)
        sql = (
            "select api_id, method, path, summary, description, tags, api_title, provider, "
            "bm25(op_fts, 0, 0, 6.0, 8.0, 2.0, 3.0, 4.0, 2.0) as rank "
            f"from op_fts where op_fts match ?{filters} order by rank limit ?"
        )
        rows = self._con.execute(sql, [*params, limit]).fetchall()
        return [
            {
                "api_id": r["api_id"],
                "api_title": r["api_title"],
                "provider": r["provider"],
                "method": r["method"],
                "path": r["path"],
                "summary": r["summary"] or None,
                "description": r["description"] or None,
                "tags": r["tags"].split() if r["tags"] else [],
                "_rank": round(float(r["rank"]), 3),
            }
            for r in rows
        ]

    def operations_for(self, api_id: str) -> list[dict[str, Any]]:
        rows = self._con.execute(
            "select method, path, summary, description, tags from op_fts where api_id = ? "
            "order by path, method",
            (api_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get(self, api_id: str) -> dict[str, Any] | None:
        row = self._con.execute("select json from apis where id = ?", (api_id,)).fetchone()
        return json.loads(row["json"]) if row else None

    def providers(self, prefix: str | None = None) -> list[dict[str, Any]]:
        sql = "select provider as name, count(*) as apis from apis"
        params: list[Any] = []
        if prefix:
            sql += " where lower(provider) like ?"
            params.append(f"{prefix.lower()}%")
        sql += " group by provider order by apis desc, provider"
        return [dict(r) for r in self._con.execute(sql, params).fetchall()]

    def categories(self) -> list[dict[str, Any]]:
        counts = dict(
            self._con.execute(
                "select category, count(*) from apis where category is not null group by category"
            ).fetchall()
        )
        return [
            {"id": key, "label": label, "apis": counts.get(key, 0)}
            for key, label in CATEGORIES.items()
        ]

    def stats(self) -> dict[str, Any]:
        meta = dict(self._con.execute("select key, value from meta").fetchall())
        by_access = dict(self._con.execute("select access, count(*) from apis group by access"))
        by_kind = dict(self._con.execute("select kind, count(*) from apis group by kind"))
        return {
            "generated_at": meta.get("generated_at"),
            "count": int(meta.get("count", 0)),
            "operations": int(meta.get("operations", 0)),
            "by_access": by_access,
            "by_source": by_kind,
        }
