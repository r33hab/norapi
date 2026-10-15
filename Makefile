UV ?= uv

.PHONY: setup lint test harvest build check search site mcp clean

setup:
	$(UV) sync

lint:
	$(UV) run ruff check src tests

test:
	$(UV) run pytest -q

harvest:          ## pull Felles datakatalog into data/raw/fdk/
	$(UV) run norapi harvest

build:            ## curated + harvested -> registry/registry.json, llms.txt, search index
	$(UV) run norapi build

enrich:           ## fetch OpenAPI documents, index their operations
	$(UV) run norapi enrich

check:            ## probe docs/spec/endpoint URLs of the curated entries
	$(UV) run norapi check --curated-only

refresh: harvest build enrich check  ## the weekly run, by hand

search:           ## make search Q="kjøretøy"
	$(UV) run norapi search "$(Q)"

site:             ## generate the static site into _site/
	$(UV) run norapi site --out _site

serve: site       ## generate with a local base URL and serve on :8000
	$(UV) run norapi site --out _site --base-url http://127.0.0.1:8000/
	cd _site && python3 -m http.server 8000

mcp:              ## run the MCP server over stdio (for a client to attach)
	$(UV) run norapi-mcp

clean:
	rm -rf data _site registry/.index.sqlite registry/.index.tmp
