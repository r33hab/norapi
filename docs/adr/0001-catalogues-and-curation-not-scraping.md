# ADR-0001: Harvest structured catalogues and curate by hand; do not scrape websites

Date: 2026-10-15. Status: accepted.

## Context

The goal is a registry of Norwegian public APIs that a developer or an AI agent can search in
seconds. The obvious shortcut is to crawl agency websites for anything that looks like an API.
That is fragile, slow to keep current, and runs into terms of use on several sites.

## Decision

- The bulk comes from Felles datakatalog (data.norge.no), Digdir's national catalogue, where
  agencies register their own data services as DCAT-AP-NO. It has a search API and a SPARQL
  endpoint, both open, and it already holds about a thousand data services.
- Developer-grade detail (what the API is good for, how to authenticate, a first call that
  works) comes from hand-written YAML in `registry/curated/`. Curated entries override and
  extend harvested ones.
- A link checker records whether docs, spec and endpoint answer. A failed probe is recorded,
  never used to drop an entry: many endpoints reject anonymous GETs by design.
- The registry stores metadata and links only. It never stores an API's data.

## Consequences

- The harvester is a few hundred lines and a weekly cron. Quality of harvested entries follows
  the quality of what agencies register; where that is thin, a curated entry fixes it.
- APIs that are not in Felles datakatalog and not curated are missing. Adding one is a YAML
  file and a pull request.
- Geodata services (WMS, WFS) dominate the catalogue by count. They are kept, tagged by format,
  and ranked below curated entries on empty queries.
