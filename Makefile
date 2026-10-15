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

check:            ## probe docs/spec/endpoint URLs of the curated entries
	$(UV) run norapi check --curated-only

search:           ## make search Q="kjøretøy"
	$(UV) run norapi search "$(Q)"

site:             ## serve the static site locally on :8000
	cp registry/registry.json registry/llms.txt site/
	cd site && python3 -m http.server 8000

mcp:              ## run the MCP server over stdio (for a client to attach)
	$(UV) run norapi-mcp

clean:
	rm -rf data registry/.index.sqlite registry/.index.tmp site/registry.json site/llms.txt
