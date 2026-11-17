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


def test_retired_entries_are_left_out_of_the_harvest(tmp_path, snapshot):
    import pytest

    from norapi.curated import drop_retired, load_retired

    retired_file = tmp_path / "retired.yaml"
    retired_file.write_text(
        "checked: 2026-11-10\nentries:\n"
        "  - uri: https://dataservice-catalog.fellesdatakatalog.digdir.no/data-services/ddd\n"
        "    reason: Vertsnavnet finnes ikke lenger.\n",
        encoding="utf-8",
    )
    harvested = fdk.to_entries(snapshot)
    kept = drop_retired(harvested, load_retired(retired_file))
    assert len(kept) == len(harvested) - 1
    assert all(not e.source["uri"].endswith("/ddd") for e in kept)
    assert load_retired(tmp_path / "missing.yaml") == {}

    retired_file.write_text("entries:\n  - uri: https://x.no/a\n", encoding="utf-8")
    with pytest.raises(ValueError, match="reason"):
        load_retired(retired_file)


def test_retained_entries_are_added_unless_the_harvest_has_them(tmp_path, snapshot):
    from norapi.curated import add_retained, load_retained

    harvested = fdk.to_entries(snapshot)
    existing_uri = harvested[0].source["uri"]

    retained_file = tmp_path / "retained.yaml"
    retained_file.write_text(
        "checked: 2026-11-17\n"
        "entries:\n"
        "  - id: ghost-service\n"
        "    title: Ghost service\n"
        "    provider:\n"
        "      name: Testetaten\n"
        "    access: open\n"
        "    auth: none\n"
        "    endpoints:\n"
        "      - https://ghost.example.no/api\n"
        "    uri: https://ghost.example.no/api\n"
        "  - id: already-here\n"
        "    title: Already here\n"
        "    provider:\n"
        "      name: Testetaten\n"
        f"    endpoints:\n      - {existing_uri}\n"
        f"    uri: {existing_uri}\n",
        encoding="utf-8",
    )

    retained, checked = load_retained(retained_file)
    assert checked == "2026-11-17"

    out = add_retained(harvested, retained, checked)
    ghosts = [e for e in out if e.id == "ghost-service"]
    assert len(ghosts) == 1
    assert ghosts[0].source["kind"] == "fdk-delisted"
    assert "no-longer-in-catalogue" in ghosts[0].tags
    assert any("Felles datakatalog" in c for c in ghosts[0].caveats)
    # one already in the harvest is not re-added
    assert not any(e.id == "already-here" for e in out)
    assert load_retained(tmp_path / "missing.yaml") == ([], "")
