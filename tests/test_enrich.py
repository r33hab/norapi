import json

import httpx

from norapi.enrich import (
    SpecFetcher,
    candidate_urls,
    neighbour_urls,
    normalise_url,
    operations,
    parse_document,
    summarise,
    urls_from_page,
)
from norapi.model import ApiEntry, Provider


def test_operations_and_summary_from_openapi_3(fixtures):
    document = json.loads((fixtures / "specs" / "petstore-openapi.json").read_text())
    ops = list(operations(document, "x"))
    assert [(o["method"], o["path"]) for o in ops] == [
        ("GET", "/kjoretoy/{kjennemerke}"),
        ("GET", "/kjoretoy"),
        ("POST", "/kjoretoy"),
        ("GET", "/health"),
    ]
    first = ops[0]
    assert first["summary"] == "Hent kjøretøy etter kjennemerke"
    assert first["description"] == "Tekniske data for ett kjøretøy. Krever API-nøkkel."
    assert first["tags"] == ["Kjøretøy"] and first["operation_id"] == "hentKjoretoy"
    assert ops[2]["deprecated"] is True

    summary = summarise(document, "https://x/openapi.json", "2026-10-15T00:00:00+00:00")
    assert summary["format"] == "openapi 3.0.1"
    assert summary["title"] == "Kjøretøy API" and summary["version"] == "2.1.0"
    assert summary["servers"] == ["https://api.example.invalid/kjoretoy/v2"]
    assert summary["operations"] == 4 and summary["tags"] == ["Kjøretøy", "Søk"]


def test_swagger_2_server_is_built_from_host_and_base_path():
    document = {
        "swagger": "2.0",
        "info": {"title": "T"},
        "host": "api.x.no",
        "basePath": "/v1",
        "schemes": ["https"],
        "paths": {"/a": {"get": {}}},
    }
    summary = summarise(document, "u", "t")
    assert summary["servers"] == ["https://api.x.no/v1"] and summary["format"] == "swagger 2.0"


def test_parse_document_accepts_json_and_yaml_and_rejects_html():
    assert (
        parse_document('{"openapi":"3.0.0","paths":{}}', "application/json")["openapi"] == "3.0.0"
    )
    assert parse_document("openapi: 3.1.0\npaths:\n  /x: {}\n", "text/plain")["paths"] == {"/x": {}}
    assert parse_document("<html><body>Swagger UI</body></html>", "text/html") is None
    assert parse_document('{"foo": 1}', "application/json") is None, "no paths: not a spec"


def test_parse_document_makes_yaml_json_safe():
    text = (
        "openapi: 3.0.0\ninfo:\n  version: 2024-01-15\n"
        "paths:\n  /x:\n    get:\n      responses:\n        200: {description: ok}\n"
    )
    document = parse_document(text, "text/yaml")
    assert document["info"]["version"] == "2024-01-15", "unquoted dates become strings"
    assert "200" in document["paths"]["/x"]["get"]["responses"], "status codes become string keys"
    json.dumps(document)  # the enrich cache writes the document as JSON


def test_url_helpers():
    assert (
        normalise_url("https://app.swaggerhub.com/apis/o/a/1.0")
        == "https://api.swaggerhub.com/apis/o/a/1.0"
    )
    page = '<script>window.ui = SwaggerUIBundle({ url: "/v3/api-docs", dom_id: "#x" })</script>'
    assert urls_from_page(page, "https://x.no/swagger-ui/index.html") == [
        "https://x.no/v3/api-docs"
    ]
    neighbours = neighbour_urls("https://x.no/docs/swagger-ui.html")
    assert neighbours[0] == "https://x.no/docs/openapi.json"
    assert "https://x.no/v3/api-docs" in neighbours


def test_candidate_urls_use_spec_url_then_swagger_like_docs():
    entry = ApiEntry(
        id="a",
        title="A",
        provider=Provider(name="P"),
        spec_url="https://x.no/openapi.json",
        docs_url="https://x.no/swagger-ui.html",
    )
    assert candidate_urls(entry) == ["https://x.no/openapi.json", "https://x.no/swagger-ui.html"]
    plain = ApiEntry(
        id="b", title="B", provider=Provider(name="P"), docs_url="https://x.no/om-apiet"
    )
    assert candidate_urls(plain) == []


def test_fetcher_follows_a_swagger_ui_page_to_its_document(fixtures):
    document = (fixtures / "specs" / "petstore-openapi.json").read_text()

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/swagger-ui/index.html":
            return httpx.Response(
                200,
                text='<html><script src="./swagger-initializer.js"></script></html>',
                headers={"content-type": "text/html"},
            )
        if request.url.path == "/swagger-ui/swagger-initializer.js":
            return httpx.Response(
                200,
                text='window.ui = SwaggerUIBundle({url: "/v3/api-docs"})',
                headers={"content-type": "application/javascript"},
            )
        if request.url.path == "/v3/api-docs":
            return httpx.Response(200, text=document, headers={"content-type": "application/json"})
        return httpx.Response(404)

    fetcher = SpecFetcher(client=httpx.Client(transport=httpx.MockTransport(handler)))
    resolved = fetcher.resolve("https://x.no/swagger-ui/index.html")
    assert resolved is not None
    url, doc = resolved
    assert url == "https://x.no/v3/api-docs" and doc["info"]["title"] == "Kjøretøy API"


def test_fetcher_gives_up_within_budget():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request.url.path)
        return httpx.Response(
            200, text="<html>nothing here</html>", headers={"content-type": "text/html"}
        )

    fetcher = SpecFetcher(client=httpx.Client(transport=httpx.MockTransport(handler)))
    assert fetcher.resolve("https://x.no/docs/swagger") is None
    assert len(calls) <= 8
