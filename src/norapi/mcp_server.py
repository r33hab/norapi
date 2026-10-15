"""MCP server so an AI assistant can look up Norwegian public APIs mid-task.

Run over stdio: `norapi-mcp`.
Claude Code: `claude mcp add norapi -- uv run --directory <repo> norapi-mcp`.
"""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

from norapi.search import Registry

INSTRUCTIONS = (
    "norapi is a registry of Norwegian public-sector APIs (and a few open private ones), "
    "harvested from Felles datakatalog (data.norge.no) plus curated entries with examples. "
    "Use search_apis with Norwegian or English words for the data you need (for example "
    "'kjøretøy', 'company register', 'weather forecast'). Filter access='open' and "
    "auth='none' when the caller wants something usable without an agreement. Every result "
    "carries docs_url, spec_url and endpoints; curated results also carry quick_start. The "
    "registry is metadata: always read the API's own documentation and terms before use."
)

mcp = FastMCP("norapi", instructions=INSTRUCTIONS)


@mcp.tool()
def search_apis(
    query: str,
    limit: int = 10,
    access: str | None = None,
    auth: str | None = None,
    provider: str | None = None,
    format: str | None = None,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """Full-text search over Norwegian public APIs.

    query: free text, Norwegian or English. access: open | restricted | non-public | unknown.
    auth: none | api-key | maskinporten | id-porten | oauth2 | unknown. provider: substring of
    the organisation name. format: JSON, XML, WMS, ... category: see list_categories.
    """
    registry = Registry.open()
    try:
        results = registry.search(
            query,
            limit=limit,
            access=access,
            provider=provider,
            fmt=format,
            category=category,
            auth=auth,
        )
    finally:
        registry.close()
    return [_compact(api) for api in results]


@mcp.tool()
def get_api(id: str) -> dict[str, Any]:
    """Everything the registry knows about one API, by its id from search_apis."""
    registry = Registry.open()
    try:
        api = registry.get(id)
    finally:
        registry.close()
    return api or {"error": f"no API with id {id!r}"}


@mcp.tool()
def list_providers(prefix: str | None = None) -> list[dict[str, Any]]:
    """Organisations in the registry with their API counts, optionally filtered by name prefix."""
    registry = Registry.open()
    try:
        return registry.providers(prefix)
    finally:
        registry.close()


@mcp.tool()
def list_categories() -> list[dict[str, Any]]:
    """Category ids and labels, with API counts (curated entries carry categories)."""
    registry = Registry.open()
    try:
        return registry.categories()
    finally:
        registry.close()


def _compact(api: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "id",
        "title",
        "summary",
        "access",
        "auth",
        "formats",
        "docs_url",
        "spec_url",
        "endpoints",
        "category",
        "quick_start",
        "license",
    )
    compact = {k: api.get(k) for k in keys if api.get(k) not in (None, [], "")}
    compact["provider"] = api["provider"]["name"]
    return compact


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
