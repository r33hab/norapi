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


def test_access_review_fills_only_what_the_catalogues_leave_blank(tmp_path, snapshot):
    from norapi.curated import apply_access_review, load_access_review

    review_file = tmp_path / "access-review.yaml"
    review_file.write_text(
        "checked: 2026-10-21\nentries:\n"
        "  - uri: https://dataservice-catalog.fellesdatakatalog.digdir.no/data-services/ddd\n"
        "    access: restricted\n    auth: api-key\n    reason: Svarer 401 uten nøkkel.\n"
        "    caveats: [Krever nøkkel.]\n"
        "  - uri: https://dataservice-catalog.fellesdatakatalog.digdir.no/data-services/aaa\n"
        "    access: open\n    reason: Skal ikke brukes, katalogen har en verdi.\n",
        encoding="utf-8",
    )
    entries = {e.source["uri"].rsplit("/", 1)[1]: e for e in fdk.to_entries(snapshot)}
    apply_access_review(list(entries.values()), load_access_review(review_file))

    oslo = entries["ddd"]
    assert (oslo.access, oslo.auth, oslo.caveats) == ("restricted", "api-key", ["Krever nøkkel."])
    assert oslo.source["access_from"] == "review"
    assert oslo.source["access_checked"] == "2026-10-21"
    assert entries["aaa"].access == "restricted", "the catalogue's own value wins"
    assert load_access_review(tmp_path / "missing.yaml") == {}
