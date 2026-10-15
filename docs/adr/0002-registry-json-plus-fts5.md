# ADR-0002: registry.json is the product; SQLite FTS5 is a derived index

Date: 2026-10-15. Status: accepted.

## Context

The registry must be usable from a CLI, an MCP server, a static web page and a language
model, with no service to run and no database to install.

## Decision

- `registry/registry.json` is committed and is the single distributable: one document, every
  entry, stable ids. The static site loads it directly; `llms.txt` is a compact rendering of it.
- Search runs on an SQLite FTS5 index built from registry.json on first use and rebuilt when
  the JSON is newer. It is a cache, ignored by git, about a second to build.
- Ranking: bm25 with heavier weight on title, provider and keywords than on description.
  Terms are prefix-matched so "kjøretøy" finds "kjøretøyopplysninger". Diacritics are folded
  so "vaer" matches "vær".

## Consequences

- Cloning the repo is enough to search; `pip install` is enough to serve the MCP server.
- Full-text search quality is bounded by FTS5. If the registry grows past tens of thousands of
  entries or needs semantic search, embeddings can be added next to the index without touching
  the JSON contract.
