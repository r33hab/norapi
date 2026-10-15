# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com), newest first, grouped by date.

## 2026-10-15
### Added
- Harvester for Felles datakatalog (data.norge.no): search API for the list, SPARQL per predicate for endpoints, specs, docs, licences and keywords, joined on the data service URI.
- Curated entries for about 35 well-known APIs (BRREG, SSB, Entur, MET, Kartverket, Nav, Skatteetaten, Digdir, Altinn, Vegvesen, Norges Bank, Stortinget, NVE and more) with access, auth, formats, docs and quick-start calls.
- Merge rules: curated fields win, harvested fields fill gaps, matched by FDK URI or identical endpoint.
- Build: `registry/registry.json`, `registry/llms.txt` for language models, and an SQLite FTS5 index rebuilt on demand.
- CLI `norapi harvest|build|check|search|show|providers|categories|stats` and an MCP server (`norapi-mcp`) with `search_apis`, `get_api`, `list_providers`, `list_categories`.
- Link checker that records docs/spec/endpoint status per entry.
- Static search site in `site/` with a GitHub Pages workflow, CI, and a weekly harvest workflow.
