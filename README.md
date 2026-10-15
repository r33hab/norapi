# norapi

> **Status: unfinished and under active development.** The harvester, the curated entries,
> the search index, the CLI and the MCP server work. Entry ids and the JSON shape may still
> change, and the curated list is short. See the roadmap.

A fast, searchable registry of Norwegian public APIs, for developers and AI agents.

- **About a thousand APIs** harvested from [Felles datakatalog](https://data.norge.no/data-services),
  the national catalogue where agencies register their data services.
- **Curated entries** for the APIs people actually reach for (Brønnøysundregistrene, SSB, Entur,
  MET, Kartverket, Nav, Skatteetaten, Digdir, Vegvesen, Norges Bank, Stortinget …) with access,
  authentication, formats, docs and a first call that works.
- **Three front doors:** a CLI, an MCP server for AI assistants, and a static web page.
  Plus `registry/llms.txt` for pasting into a language model's context.

```
registry/curated/*.yaml ──┐
                          ├─▶ norapi build ─▶ registry/registry.json ─┬─▶ norapi search   (CLI)
data.norge.no ─▶ norapi   │                   registry/llms.txt       ├─▶ norapi-mcp      (AI agents)
  harvest ────────────────┘                   .index.sqlite (FTS5)    └─▶ site/index.html (web)
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

The committed `registry/registry.json` is used as is. To refresh it from the catalogue:

```sh
uv run norapi harvest          # data.norge.no -> data/raw/fdk/fdk.json (about 30 seconds)
uv run norapi build            # curated + harvested -> registry/
uv run norapi check --curated-only   # probe docs, spec and endpoint URLs, record the status
```

## For AI assistants

`norapi-mcp` is an [MCP](https://modelcontextprotocol.io) server over stdio with four tools:
`search_apis`, `get_api`, `list_providers`, `list_categories`.

```sh
# Claude Code
claude mcp add norapi -- uv run --directory /path/to/norapi norapi-mcp
```

Any MCP client works the same way. Without MCP, `registry/llms.txt` is a one-line-per-API
Markdown listing you can drop into a prompt.

## Web

`site/index.html` is a single file that loads `registry.json` and searches client-side.
`make site` serves it locally; the `pages` workflow publishes it to GitHub Pages on every push.

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

1. Add it to a file in `registry/curated/` (one file per provider, see `brreg.yaml` for the shape).
   If the API is already in Felles datakatalog, set `merge_with` to its data service URI, or
   list the same endpoint URL, and the two are merged with your fields on top.
2. `uv run norapi build && uv run norapi check --curated-only`
3. `uv run pytest -q`, then open a pull request.

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

- Fetch OpenAPI documents where `spec_url` points to one and index endpoint paths and summaries,
  so a search can land on an operation, not only an API.
- More curated entries, English summaries for all of them, and a contribution guide.
- Harvest Geonorge's kartkatalog directly for richer geodata entries.
- Weekly link checks published on the site.

## Licence

Code and curated descriptions: MIT. Harvested metadata: see Felles datakatalog.
