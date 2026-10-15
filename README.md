# norapi

> **Status: unfinished and under active development.** The harvester, the curated entries,
> the OpenAPI enrichment, the search index, the CLI, the MCP server and the site work.
> Entry ids and the JSON shape may still change, and the curated list wants to grow:
> see [Bidra](https://r33hab.github.io/norapi/bidra/) and [CONTRIBUTING.md](CONTRIBUTING.md).

A fast, searchable registry of Norwegian public APIs, for developers and AI agents.
**Live site: [r33hab.github.io/norapi](https://r33hab.github.io/norapi/)**

- **About a thousand APIs** harvested from [Felles datakatalog](https://data.norge.no/data-services),
  the national catalogue where agencies register their data services.
- **Curated entries** for the APIs people actually reach for (Brønnøysundregistrene, SSB, Entur,
  MET, Kartverket, Nav, Skatteetaten, Digdir, Vegvesen, Norges Bank, Stortinget, Udir, FHI …)
  with access, authentication, formats, docs and a first call that works.
- **Operations, not only APIs.** Where an entry links an OpenAPI document, the document is fetched
  and every operation is indexed, so a search can land on `GET /vegobjekter/{id}`.
- **Four front doors:** a CLI, an MCP server for AI assistants, a static site with one page per
  API, and `registry/llms.txt` for pasting into a language model's context.

```
registry/curated/*.yaml ──┐                 registry/registry.json ─┬─▶ norapi search / ops  (CLI)
data.norge.no ─▶ harvest ─┼─▶ norapi build ─▶ registry/llms.txt     ├─▶ norapi-mcp           (AI agents)
OpenAPI docs ──▶ enrich ──┘                 registry/operations.json└─▶ norapi site ─▶ _site/ (web)
```

## Quick start

```sh
git clone https://github.com/r33hAB/norapi && cd norapi
uv sync

uv run norapi search "kjøretøy"                 # full text, Norwegian or English
uv run norapi search "weather" --access open --auth none
uv run norapi search "" --provider skatteetaten --limit 50
uv run norapi show brreg-enhetsregisteret       # everything, including a quick_start call
uv run norapi providers | head
```

```sh
uv run norapi ops "vegobjekter"                 # operations: method + path + summary, with the API
```

The committed `registry/` files are used as is. To refresh them:

```sh
uv run norapi harvest                # data.norge.no -> data/raw/fdk/fdk.json (about 30 seconds)
uv run norapi build                  # curated + harvested (+ cached specs) -> registry/
uv run norapi enrich                 # fetch OpenAPI documents -> registry/specs.json, operations.json
uv run norapi check --curated-only   # probe docs, spec and endpoint URLs, record the status
uv run norapi site --out _site       # the static site
```

## For AI assistants

`norapi-mcp` is an [MCP](https://modelcontextprotocol.io) server over stdio with five tools:
`search_apis`, `search_operations`, `get_api`, `list_providers`, `list_categories`.

```sh
# Claude Code
claude mcp add norapi -- uv run --directory /path/to/norapi norapi-mcp
```

Any MCP client works the same way. Without MCP, `registry/llms.txt` is a one-line-per-API
Markdown listing you can drop into a prompt.

## Web

`norapi site` renders one static page per API, provider and category, plus the index with
client-side search and a ⌘K palette, a sitemap, robots.txt, JSON-LD and Open Graph tags.
`make serve` previews it locally; the `pages` workflow publishes it to GitHub Pages on every push.
Design tokens and the Hallmark stamp live in `site/assets/`.

## Entry shape

| Field | Meaning |
|---|---|
| `id` | stable slug, `provider-title` |
| `title`, `title_en`, `summary`, `description` | what the API is; `summary` is one line for search results and models |
| `provider` | name, orgnr, sector (`stat`, `kommune`, `fylke`, `statlig-selskap`, `privat`) |
| `access` | `open`, `restricted`, `non-public`, `unknown` |
| `auth` | `none`, `api-key`, `maskinporten`, `id-porten`, `oauth2`, `unknown` |
| `formats`, `endpoints`, `spec_url`, `docs_url`, `license`, `keywords` | the links and facts you need to start |
| `category`, `tags`, `quick_start`, `probe_url` | curated only; `probe_url` is a call that answers anonymously, used by `norapi check` |
| `source` | `fdk`, `curated` or `curated+fdk`, with the catalogue URI and harvest time |
| `checks` | last link-check result per URL, when `norapi check` has run |

## Adding or fixing an API

There must be more open Norwegian APIs than this registry knows about. Three ways in:

1. **No code:** [suggest an API](https://github.com/r33hAB/norapi/issues/new?template=nytt-api.yml)
   or [report a mistake](https://github.com/r33hAB/norapi/issues/new?template=feil-i-oppforing.yml).
2. **A pull request:** add it to a file in `registry/curated/` (one file per provider, see
   `brreg.yaml` for the shape). If the API is already in Felles datakatalog, set `merge_with` to
   its data service URI, or list the same endpoint URL, and the two are merged with your fields on top.
   Then `uv run norapi build && uv run norapi check --curated-only && uv run pytest -q`.
3. **Register it at [data.norge.no](https://data.norge.no/data-services)** if you are the provider;
   the weekly harvest picks it up from there.

Details and the quality bar are in [CONTRIBUTING.md](CONTRIBUTING.md).

## Data sources and terms

Harvested metadata comes from Felles datakatalog, operated by Digitaliseringsdirektoratet;
each entry links back to its catalogue page. The registry holds descriptions and links, not the
APIs' data. Every API has its own terms and licence, and the registry only reports what the
catalogue or the curator wrote down. Nothing here is scraped from agency websites
([ADR-0001](docs/adr/0001-catalogues-and-curation-not-scraping.md)).

## Layout

```
src/norapi/
  harvest/fdk.py     Felles datakatalog: search API + SPARQL, raw snapshot to data/raw/
  curated.py         registry/curated/*.yaml and the merge rules
  model.py           ApiEntry, categories, normalisation
  build.py           registry.json, llms.txt, FTS5 index
  search.py          ranked search with filters
  check.py           link checker
  cli.py / mcp_server.py
registry/
  curated/           hand-written entries, one YAML per provider
  registry.json      the built registry (committed)
  llms.txt           one line per API, for language models (committed)
site/index.html      static search page
tests/               unit tests on recorded fixtures
docs/adr/            decisions
```

## Roadmap

- More curated entries, and English summaries for all of them.
- Harvest Geonorge's kartkatalog directly for richer geodata entries.
- Weekly link checks for every entry, published on the site.
- Semantic search next to FTS5 once the registry outgrows keyword matching.

## Licence

Code and curated descriptions: MIT. Harvested metadata: see Felles datakatalog.
