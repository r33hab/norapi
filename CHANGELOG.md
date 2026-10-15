# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com), newest first, grouped by date.

## 2026-10-15
### Added
- OpenAPI enrichment (`norapi enrich`): resolves specifications behind `spec_url` and Swagger UI pages, caches the documents, writes `registry/specs.json` and `registry/operations.json`, and indexes every operation so `norapi ops` and the MCP tool `search_operations` can land on a method and path.
- Static site generator (`norapi site`): one pre-rendered page per API, provider and category, index with client-side search and a ⌘K palette, contribute and privacy pages, custom 404, sitemap, robots.txt, canonical and Open Graph tags, JSON-LD (WebSite, Dataset, WebAPI, Organization, BreadcrumbList). Hallmark design (Cobalt theme, Ecosystem Index) with tokens in `site/assets/tokens.css`.
- Fourteen more curated APIs after a source review: Statnett driftsdata, Udir Grep, HK-dir DBH, FHI Statistikk, Helsedirektoratet HAPI, Vinmonopolet, Luftfartstilsynet dronesoner, Ordbøkene, DigitaltMuseum, Kartverket høydedata, WMTS and vannstand, Frivillighetsregisteret, Entur rutedata, Digdir KRR.
- Contribution path: CONTRIBUTING.md, issue forms for new APIs and corrections, a pull request template, and a "Bidra" page on the site.
- `probe_url` on curated entries so the link checker can call an endpoint that answers anonymously.
### Changed
- Pages workflow now generates the site with `norapi site`; the weekly harvest also runs `norapi enrich`.
- Link checker reports verdicts (ok / answers / missing) instead of raw status codes.
- README rewritten as a proper front page: banner, live badges from registry.json, screenshot, the four front doors, pipeline and entry shape.
### Security
- All outbound fetches (spec fetcher, link checker) go through `netguard`: http(s) only, hosts resolved and checked against private, loopback and link-local ranges, the validated address pinned for the connect (no DNS rebinding window), every redirect hop validated before it is requested, bodies read through a streamed cap.
- JSON-LD escapes angle brackets and ampersands; external links render only for http(s) URLs; operation methods from third-party specs are escaped in the client-side search; entry ids must be slugs before they become file paths.
### Fixed
- `norapi enrich --limit N` merges into the existing specs and operations instead of overwriting them with the subset.
- Harvester for Felles datakatalog (data.norge.no): search API for the list, SPARQL per predicate for endpoints, specs, docs, licences and keywords, joined on the data service URI.
- Curated entries for about 35 well-known APIs (BRREG, SSB, Entur, MET, Kartverket, Nav, Skatteetaten, Digdir, Altinn, Vegvesen, Norges Bank, Stortinget, NVE and more) with access, auth, formats, docs and quick-start calls.
- Merge rules: curated fields win, harvested fields fill gaps, matched by FDK URI or identical endpoint.
- Build: `registry/registry.json`, `registry/llms.txt` for language models, and an SQLite FTS5 index rebuilt on demand.
- CLI `norapi harvest|build|check|search|show|providers|categories|stats` and an MCP server (`norapi-mcp`) with `search_apis`, `get_api`, `list_providers`, `list_categories`.
- Link checker that records docs/spec/endpoint status per entry.
- Static search site in `site/` with a GitHub Pages workflow, CI, and a weekly harvest workflow.
