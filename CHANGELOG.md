# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com), newest first, grouped by date.

## 2026-10-19
### Added
- Thirty more curated APIs, each probed live and with a quick start that was run: Lovdata open datasets, eInnsyn, Elhub energy data, Nav grunnbeløp, Matvaretabellen, Varsom, Regobs, NVE GridTimeSeries and magasinstatistikk, Entur Mobility v2 and vehicle positions, SSB PxWebApi 2, Sikt NVA and Cristin, NB DH-lab, KulturNav, Tolletaten open data, Arbeidstilsynet renholdsregisteret, Udir school and kindergarten registers, Fiskeridirektoratet vessel and aquaculture registers, Miljødirektoratet air quality, Finanstilsynet registry, plus keyed or registration-only APIs: Doffin, NOBIL, Enova's data portal, Vegvesen DATEX II, Patentstyret and Kassalapp.
- Nine of them curate entries that were only harvested before (`merge_with` on the catalogue URI), so the raw Felles datakatalog rows get proper descriptions, docs and quick starts.
### Changed
- DigitaltMuseum moved from the Nasjonalbiblioteket file to a new KulturIT provider file, next to KulturNav; its id is unchanged.
### Fixed
- `norapi enrich` crashed with "Object of type date is not JSON serializable" on YAML specs with unquoted dates; YAML documents now go through a JSON round trip when parsed, which also turns integer status-code keys into strings like a JSON spec has.
- `norapi build` failed with "UNIQUE constraint failed: apis.id" when the Felles datakatalog search API returned one data service on two pages; the harvester now keeps one entry per catalogue URI.
### Security
- YAML specs can no longer exhaust memory through alias expansion or nested `<<` merge keys: the composed node graph is measured before the document is built and refused past two million expanded nodes, self-referencing aliases are rejected, and the JSON round trip also stops past four times the 8 MB fetch cap. A spec with a mapping key JSON cannot hold, such as an unquoted date, is skipped instead of crashing the run.

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
- All outbound fetches (spec fetcher, link checker) go through `netguard`: http(s) only, hosts resolved and checked against private, loopback and link-local ranges, every redirect hop validated before it is requested, bodies read through a streamed cap.
- Address pinning happens in the TCP layer (`PinningBackend`), so the URL keeps its hostname and TLS verifies the certificate against it; a lying resolver now fails the handshake with a hostname mismatch instead of being trusted. An earlier variant put the address in the URL, which weakened that check.
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
