import json

from norapi.build import write_registry
from norapi.curated import load_curated, merge
from norapi.harvest import fdk
from norapi.site import generate_site


def _registry_dir(tmp_path, fixtures, snapshot):
    entries = merge(load_curated(fixtures / "curated"), fdk.to_entries(snapshot))
    registry_dir = tmp_path / "registry"
    registry_dir.mkdir()
    write_registry(entries, registry_dir / "registry.json")
    (registry_dir / "operations.json").write_text(
        json.dumps(
            {
                "generated_at": "2026-10-15T00:00:00+00:00",
                "count": 2,
                "operations": [
                    {
                        "api_id": "geonorge-kommuneinfo",
                        "method": "GET",
                        "path": "/kommuner",
                        "summary": "Alle kommuner",
                        "tags": ["Kommuner"],
                    },
                    {
                        "api_id": "geonorge-kommuneinfo",
                        "method": "GET",
                        "path": "/punkt",
                        "summary": "Kommune for et punkt",
                        "tags": ["Kommuner"],
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    return registry_dir


def test_generate_site_writes_every_page_and_the_machine_files(tmp_path, fixtures, snapshot):
    registry_dir = _registry_dir(tmp_path, fixtures, snapshot)
    out = tmp_path / "_site"

    written = generate_site(registry_dir, out, base_url="https://example.invalid/norapi")

    assert written > 10
    assert (out / "index.html").exists() and (out / "404.html").exists()
    assert (out / "api" / "geonorge-kommuneinfo" / "index.html").exists()
    assert (out / "leverandor" / "kartverket" / "index.html").exists()
    assert (out / "kategori" / "kart-og-geodata" / "index.html").exists()
    assert (out / "bidra" / "index.html").exists() and (out / "personvern" / "index.html").exists()
    assert (out / "assets" / "style.css").exists() and (out / "assets" / "app.js").exists()
    assert (out / "registry.json").exists() and (out / "llms.txt").exists()
    assert (out / ".nojekyll").exists()

    robots = (out / "robots.txt").read_text()
    assert "Sitemap: https://example.invalid/norapi/sitemap.xml" in robots
    sitemap = (out / "sitemap.xml").read_text()
    assert sitemap.count("<url>") == 1 + 5 + 3 + 1 + 1 + 2, (
        "index + apis + providers + list + category + 2 pages"
    )
    assert "<loc>https://example.invalid/norapi/api/test-standalone/</loc>" in sitemap


def test_api_page_has_seo_essentials_and_operations(tmp_path, fixtures, snapshot):
    registry_dir = _registry_dir(tmp_path, fixtures, snapshot)
    out = tmp_path / "_site"
    generate_site(registry_dir, out, base_url="https://example.invalid/norapi/")
    page = (out / "api" / "geonorge-kommuneinfo" / "index.html").read_text()

    assert page.count("<h1") == 1
    assert (
        '<link rel="canonical" href="https://example.invalid/norapi/api/geonorge-kommuneinfo/">'
        in page
    )
    assert "<title>Kommuneinfo-API (Geonorge) (Kartverket) · norapi</title>" in page
    assert 'property="og:title"' in page and 'name="description"' in page
    assert '"@type": "WebAPI"' in page and '"@type": "BreadcrumbList"' in page
    assert "GET" in page and "/kommuner" in page and "Alle kommuner" in page
    assert "Kopier" in page, "quick start comes with a copy button"
    assert "feil-i-oppforing.yml" in page
    assert 'href="https://example.invalid/norapi/leverandor/kartverket/"' in page
    assert "Forbehold" not in page, "no caveats, no warning box"


def test_caveats_show_on_the_api_page_and_in_search(tmp_path, fixtures, snapshot):
    registry_dir = _registry_dir(tmp_path, fixtures, snapshot)
    out = tmp_path / "_site"
    generate_site(registry_dir, out, base_url="https://example.invalid/norapi/")
    page = (out / "api" / "test-standalone" / "index.html").read_text()

    assert '<section class="caveats"' in page
    assert "<li>Testforbehold, vises som Forbehold.</li>" in page
    assert '<span class="badge badge--caveat">Forbehold</span>' in page
    rows = {r["id"]: r for r in json.loads((out / "search-index.json").read_text())}
    assert rows["test-standalone"]["w"] == 1 and "w" not in rows["geonorge-kommuneinfo"]


def test_index_has_one_h1_search_and_real_counts(tmp_path, fixtures, snapshot):
    registry_dir = _registry_dir(tmp_path, fixtures, snapshot)
    out = tmp_path / "_site"
    generate_site(registry_dir, out, base_url="https://example.invalid/norapi/")
    index = (out / "index.html").read_text()
    assert index.count("<h1") == 1
    assert 'id="q"' in index and 'id="cmdk"' in index
    assert "<dd>5</dd>" in index, "API count comes from the registry, not a made-up number"
    assert '"@type": "WebSite"' in index and "SearchAction" in index
    search_index = json.loads((out / "search-index.json").read_text())
    assert {row["id"] for row in search_index} == {
        "geonorge-kommuneinfo",
        "test-standalone",
        "skatteetaten-mva-melding-api",
        "kartverket-kommuneinfo-"
        + next(
            r["id"] for r in search_index if r["id"].startswith("kartverket-kommuneinfo-")
        ).rsplit("-", 1)[1],
        "oslo-kommune-byradssaker",
    }
    ops_index = json.loads((out / "ops-index.json").read_text())
    assert ops_index[0]["a"] == "geonorge-kommuneinfo" and ops_index[0]["m"] == "GET"


def test_api_page_says_where_the_access_value_came_from(tmp_path, fixtures, snapshot):
    registry_dir = _registry_dir(tmp_path, fixtures, snapshot)
    registry_json = registry_dir / "registry.json"
    document = json.loads(registry_json.read_text())
    harvested = next(a for a in document["apis"] if a["source"]["kind"] == "fdk")
    harvested["source"].update(
        access_from="review", access_checked="2026-10-21", access_note="Svarer 401 uten nøkkel."
    )
    registry_json.write_text(json.dumps(document), encoding="utf-8")
    out = tmp_path / "_site"
    generate_site(registry_dir, out, base_url="https://example.invalid/norapi/")
    page = (out / "api" / harvested["id"] / "index.html").read_text()

    assert "sjekket for hånd 2026-10-21: Svarer 401 uten nøkkel." in page
