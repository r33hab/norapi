import pytest

from norapi.harvest import fdk
from norapi.model import ApiEntry, Provider, make_summary, normalise_format, slugify


def test_hits_become_normalised_entries(snapshot):
    entries = {e.id: e for e in fdk.to_entries(snapshot)}
    mva = entries["skatteetaten-mva-melding-api"]

    assert mva.access == "restricted"
    assert mva.auth == "maskinporten", "inferred from the description"
    assert mva.provider == Provider(
        name="Skatteetaten", orgnr="974761076", org_path="/STAT/972417807/974761076", sector="stat"
    )
    assert mva.title_en == "VAT return API"
    assert mva.endpoints == ["https://api.skatteetaten.no/mva"]
    assert mva.spec_url == "https://api.swaggerhub.com/apis/skatteetaten/mva-melding-api/1.0.0"
    assert mva.docs_url == "https://skatteetaten.github.io/api-dokumentasjon/"
    assert mva.formats == ["JSON"]
    assert mva.keywords == ["mva", "merverdiavgift"]
    assert mva.modified == "2026-07-30T12:29:35.989Z"
    assert mva.source["kind"] == "fdk"
    assert mva.source["catalogue_url"] == "https://data.norge.no/data-services/fdk-a"
    assert mva.summary.startswith("Tjenesten leverer")


def test_same_provider_and_title_get_a_stable_suffix(snapshot):
    ids = sorted(
        e.id for e in fdk.to_entries(snapshot) if e.id.startswith("kartverket-kommuneinfo")
    )
    assert ids[0] == "kartverket-kommuneinfo"
    assert ids[1].startswith("kartverket-kommuneinfo-") and len(ids[1].rsplit("-", 1)[1]) == 6
    assert ids == sorted(e.id for e in fdk.to_entries(snapshot) if "kommuneinfo" in e.id), (
        "deterministic"
    )


def test_sparse_hit_falls_back_sensibly(snapshot):
    entry = next(e for e in fdk.to_entries(snapshot) if e.provider.name == "Oslo kommune")
    assert entry.title == "Byrådssaker", "nynorsk title is used when bokmål is missing"
    assert entry.access == "unknown"
    assert entry.provider.sector == "kommune"
    assert entry.summary == "Byrådssaker", "no description: summary is the title"
    assert entry.spec_url is None
    assert entry.docs_url == "https://example.oslo.kommune.no/om-apiet", (
        "non-spec endpoint description"
    )


def test_endpoint_description_that_is_a_spec_is_not_reused_as_docs(snapshot):
    entry = next(e for e in fdk.to_entries(snapshot) if e.id == "kartverket-kommuneinfo")
    assert entry.spec_url == "https://ws.geonorge.no/kommuneinfo/v1/static/openapi_doc.json"
    assert entry.docs_url is None
    assert entry.license == "http://publications.europa.eu/resource/authority/licence/CC_BY_4_0"
    assert entry.formats == ["JSON"], "EU file-type URI and media type collapse to one format"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("MEDIA_TYPE application/json", "JSON"),
        ("FILE_TYPE JSON", "JSON"),
        ("http://publications.europa.eu/resource/authority/file-type/CSV", "CSV"),
        ("text/turtle", "Turtle"),
        ("application/vnd.geo+json", "VND.GEO"),
        ("WMS", "WMS"),
        ("", None),
    ],
)
def test_normalise_format(raw, expected):
    assert normalise_format(raw) == expected


def test_slugify_handles_norwegian_letters():
    assert slugify("Statens vegvesen: Kjøretøy & vei (v2)") == "statens-vegvesen-kjoretoy-vei-v2"


def test_make_summary_cuts_on_a_word_boundary():
    text = "Første setning er kort. " + "ord " * 100
    summary = make_summary(text, "title", limit=60)
    assert len(summary) <= 61 and summary.endswith("…") and not summary.endswith(" …")


def test_entry_rejects_unknown_access_value():
    with pytest.raises(ValueError):
        ApiEntry(id="x", title="x", provider=Provider(name="x"), access="public")
