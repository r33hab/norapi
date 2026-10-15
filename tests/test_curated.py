from norapi.curated import load_curated, merge
from norapi.harvest import fdk


def test_load_curated_fills_summary_and_source(fixtures):
    entries = {e.id: e for e in load_curated(fixtures / "curated")}
    assert set(entries) == {"geonorge-kommuneinfo", "test-standalone"}
    standalone = entries["test-standalone"]
    assert standalone.summary.startswith("Søk i stedsnavn.")
    assert standalone.source == {
        "kind": "curated",
        "file": "kartverket-test.yaml",
        "merge_with": None,
        "updated": "2026-10-15",
    }
    assert standalone.provider.orgnr == "971040238"


def test_merge_overlays_curated_fields_on_the_matching_harvested_entry(fixtures, snapshot):
    curated = load_curated(fixtures / "curated")
    harvested = fdk.to_entries(snapshot)

    merged = {e.id: e for e in merge(curated, harvested)}

    assert len(merged) == len(curated) + len(harvested) - 1, "one harvested entry was absorbed"
    assert "kartverket-kommuneinfo" not in merged
    kommuneinfo = merged["geonorge-kommuneinfo"]
    assert kommuneinfo.source["kind"] == "curated+fdk"
    assert kommuneinfo.source["uri"].endswith("/bbb")
    assert kommuneinfo.title == "Kommuneinfo-API (Geonorge)", "curated title wins"
    assert kommuneinfo.spec_url.endswith("openapi_doc.json"), "harvested spec fills the gap"
    assert kommuneinfo.license.endswith("CC_BY_4_0"), "harvested licence fills the gap"
    assert kommuneinfo.formats == ["GeoJSON", "JSON"], "lists are unioned, curated first"
    assert kommuneinfo.quick_start.startswith("curl")
    assert merged["test-standalone"].source["kind"] == "curated"
