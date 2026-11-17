import httpx

from norapi.authprobe import (
    apply_review,
    classify,
    load_review,
    probe,
    probe_request,
    write_review,
)
from norapi.model import ApiEntry, Provider


def _entry(endpoint: str, formats: list[str] | None = None, **source) -> ApiEntry:
    return ApiEntry(
        id="e",
        title="E",
        provider=Provider(name="P"),
        endpoints=[endpoint],
        formats=formats or [],
        source={"kind": "fdk", "uri": "urn:e", **source},
    )


def test_probe_request_asks_ogc_services_for_capabilities():
    assert (
        probe_request(_entry("https://x.no/wms/kart", ["WMS"]))
        == "https://x.no/wms/kart?service=WMS&request=GetCapabilities"
    )
    assert probe_request(_entry("https://x.no/geo?service=WFS")) == (
        "https://x.no/geo?service=WFS&request=GetCapabilities"
    ), "service already given: only the request is added"
    kept = "https://x.no/wms?SERVICE=WMS&REQUEST=GetCapabilities"
    assert probe_request(_entry(kept)) == kept
    assert probe_request(_entry("https://x.no/wmts/1.0.0")).endswith(
        "service=WMTS&request=GetCapabilities"
    )


def test_probe_request_asks_arcgis_for_json():
    url = "https://x.no/arcgis/rest/services/Bytraer/MapServer"
    assert probe_request(_entry(url)) == url + "?f=json"
    assert probe_request(_entry("https://x.no/api/v1/items")) == "https://x.no/api/v1/items"


def test_classify_only_a_real_answer_means_no_auth():
    assert classify(200, "text/xml", b"<WMS_Capabilities version='1.3.0'>")[0] == "none"
    assert classify(200, "application/json", b'{"features": []}')[0] == "none"
    assert classify(200, "text/html", b"<!doctype html><title>Logg inn</title>")[0] == "unknown"
    assert classify(401, "application/json", b"")[0] == "unknown"
    assert classify(None, "", None)[0] == "unknown"
    token = b'{"error": {"code": 499, "message": "Token Required"}}'
    assert classify(200, "application/json", token) == (
        "unknown",
        "anonymous call refused (error 499: token required)",
    )
    exception = b"<ServiceExceptionReport><ServiceException>Unauthorized</ServiceException>"
    assert classify(200, "text/xml", exception)[0] == "unknown"
    assert classify(200, "application/json", None)[0] == "none", "too large to read, not HTML"


def test_probe_records_what_it_saw():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.params.get("request") == "GetCapabilities":
            return httpx.Response(
                200, text="<WMS_Capabilities/>", headers={"content-type": "text/xml"}
            )
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    entry = _entry("https://x.no/wms", ["WMS"])
    entry.access = "open"
    result = probe(client, entry)
    assert result["auth"] == "none" and result["observed"] == "GetCapabilities answers anonymously"
    entry.access = "restricted"
    assert probe(client, entry)["auth"] == "unknown", "open capabilities, restricted data"


def test_review_round_trip_fills_only_unknown_auth(tmp_path):
    path = tmp_path / "auth-review.yaml"
    write_review(
        [
            {"id": "e", "uri": "urn:e", "auth": "none", "observed": "anonymous call returns JSON"},
            {
                "id": "f",
                "uri": "urn:f",
                "auth": "unknown",
                "observed": "anonymous call refused (401)",
            },
        ],
        path,
    )
    review = load_review(path)
    unknown = _entry("https://x.no/a")
    refused = _entry("https://x.no/b", uri="urn:f")
    known = _entry("https://x.no/c")
    known.auth = "maskinporten"
    assert apply_review([unknown, refused, known], review) == 1
    assert unknown.auth == "none" and unknown.source["auth_from"] == "probe"
    assert refused.auth == "unknown", "a refusal does not say which credentials"
    assert known.auth == "maskinporten", "a value from elsewhere wins"
