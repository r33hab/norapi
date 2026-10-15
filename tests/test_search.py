import os
import time

from norapi.build import build_index, ensure_index, write_registry
from norapi.curated import load_curated, merge
from norapi.harvest import fdk
from norapi.search import Registry, fts_query


def _registry(tmp_path, fixtures, snapshot):
    entries = merge(load_curated(fixtures / "curated"), fdk.to_entries(snapshot))
    registry_json = tmp_path / "registry.json"
    write_registry(entries, registry_json)
    return registry_json, Registry.open(registry_json, tmp_path / ".index.sqlite")


def test_fts_query_quotes_and_prefix_matches_terms():
    assert fts_query("kjøretøy api") == '"kjøretøy"* "api"*'
    assert fts_query("mva") == '"mva"*'
    assert fts_query("ad") == '"ad"', "short terms are exact"
    assert fts_query('"drop table" --') == '"drop"* "table"*'
    assert fts_query("") == ""


def test_build_writes_registry_and_llms_txt(tmp_path, fixtures, snapshot):
    registry_json, registry = _registry(tmp_path, fixtures, snapshot)
    llms = (tmp_path / "llms.txt").read_text(encoding="utf-8")
    assert "## Curated" in llms and "Kommuneinfo-API (Geonorge)" in llms
    assert registry.stats()["count"] == 5
    assert registry.stats()["by_source"] == {"curated": 1, "curated+fdk": 1, "fdk": 3}


def test_search_ranks_title_matches_first_and_filters(tmp_path, fixtures, snapshot):
    _, registry = _registry(tmp_path, fixtures, snapshot)

    hits = registry.search("kommune")
    assert hits[0]["id"] == "geonorge-kommuneinfo", "curated title match outranks the rest"
    assert any(h["id"].startswith("kartverket-kommuneinfo-") for h in hits), "prefix match on title"
    assert any(h["id"].endswith("byradssaker") for h in hits), (
        "match on provider name 'Oslo kommune'"
    )

    restricted = registry.search("mva", access="restricted")
    assert [h["id"] for h in restricted] == ["skatteetaten-mva-melding-api"]
    assert registry.search("mva", access="open") == []

    by_provider = registry.search("", provider="kartverket")
    assert {h["provider"]["name"] for h in by_provider} == {"Kartverket"}
    assert by_provider[0]["source"]["kind"] != "fdk", "curated entries sort first on an empty query"

    assert [h["id"] for h in registry.search("stedsnavn", fmt="json")] == ["test-standalone"]
    assert registry.search("stedsnavn", category="statistikk") == []


def test_get_providers_and_categories(tmp_path, fixtures, snapshot):
    _, registry = _registry(tmp_path, fixtures, snapshot)
    assert registry.get("test-standalone")["title"] == "Stedsnavn-API"
    assert registry.get("nope") is None
    providers = registry.providers()
    assert providers[0] == {"name": "Kartverket", "apis": 3}
    assert registry.providers(prefix="skatte") == [{"name": "Skatteetaten", "apis": 1}]
    categories = {c["id"]: c["apis"] for c in registry.categories()}
    assert categories["kart-og-geodata"] == 2


def test_ensure_index_rebuilds_when_registry_is_newer(tmp_path, fixtures, snapshot):
    registry_json, registry = _registry(tmp_path, fixtures, snapshot)
    registry.close()
    index = tmp_path / ".index.sqlite"
    build_index(registry_json, index)
    old = os.stat(index).st_mtime
    time.sleep(0.01)
    registry_json.touch()
    ensure_index(registry_json, index)
    assert os.stat(index).st_mtime > old
