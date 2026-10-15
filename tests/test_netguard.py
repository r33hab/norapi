import httpx
import pytest

from norapi.model import ApiEntry, Provider
from norapi.netguard import MAX_BODY_BYTES, get_capped, is_public_url, read_capped
from norapi.site import _jsonld, safe_href


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/openapi.json",
        "http://127.0.0.1:8080/",
        "https://10.0.0.1/",
        "https://192.168.1.1/api",
        "http://169.254.169.254/latest/meta-data/",
        "https://[::1]/",
        "file:///etc/passwd",
        "ftp://1.1.1.1/",
        "https://",
        "not a url",
    ],
)
def test_private_or_non_http_urls_are_rejected(url):
    assert is_public_url(url) is False


def test_public_ip_literal_is_accepted():
    assert is_public_url("https://1.1.1.1/") is True


def test_get_capped_stops_at_the_limit():
    big = b"x" * 1000

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=big)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    response, body, _ = get_capped(client, "https://x.no/spec.json", limit=100)
    assert body is None, "larger than the cap: dropped, not buffered"
    response, body, _ = get_capped(client, "https://x.no/spec.json", limit=MAX_BODY_BYTES)
    assert body == big


def test_get_capped_refuses_private_targets_before_any_request():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        return httpx.Response(200, content=b"{}")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert get_capped(client, "http://127.0.0.1/spec.json") is None
    assert calls == []


def test_read_capped_counts_streamed_chunks():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"abc" * 10)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    with client.stream("GET", "https://x.no/") as response:
        assert read_capped(response, limit=5) is None


def test_entry_ids_must_be_slugs():
    for bad in ("../etc", "a b", "A", "", "x/y", "a--b-"[:-1] + "/"):
        with pytest.raises(ValueError):
            ApiEntry(id=bad, title="t", provider=Provider(name="p"))
    ApiEntry(id="a", title="t", provider=Provider(name="p"))
    ApiEntry(id="brreg-enhetsregisteret-2", title="t", provider=Provider(name="p"))


def test_jsonld_cannot_close_its_script_tag():
    text = _jsonld({"name": "</script><script>alert(1)</script>", "x": "a & b"})
    assert "<" not in text and ">" not in text and "&" not in text
    assert "\\u003c/script" in text


def test_safe_href_only_renders_http_links():
    assert safe_href("https://api.x.no/v1") == "https://api.x.no/v1"
    assert safe_href("javascript:alert(1)") == "#"
    assert safe_href(None) == "#"
    assert safe_href('https://x.no/?a=1&b="2"') == "https://x.no/?a=1&amp;b=&quot;2&quot;"


def test_redirect_into_a_private_host_is_refused_before_it_is_requested():
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if request.url.path == "/start":
            return httpx.Response(302, headers={"location": "http://169.254.169.254/latest/"})
        return httpx.Response(200, content=b"secret")

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert get_capped(client, "https://x.no/start") is None
    assert calls == ["https://x.no/start"], "the private hop was never requested"


def test_public_redirects_are_followed_and_the_logical_url_is_returned():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/old":
            return httpx.Response(301, headers={"location": "/new/openapi.json"})
        assert request.headers["host"] == "x.no"
        return httpx.Response(200, content=b'{"openapi":"3.0.0","paths":{}}')

    client = httpx.Client(transport=httpx.MockTransport(handler))
    response, body, final_url = get_capped(client, "https://x.no/old")
    assert response.status_code == 200 and body.startswith(b"{")
    assert final_url == "https://x.no/new/openapi.json"


def test_redirect_loops_give_up():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(302, headers={"location": "https://x.no/loop"})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    assert get_capped(client, "https://x.no/loop") is None


def test_pinning_backend_refuses_before_connecting(monkeypatch):
    from norapi import netguard

    monkeypatch.setattr(netguard, "public_address", lambda host, port: None)
    connected = []
    monkeypatch.setattr(
        netguard.httpcore.SyncBackend, "connect_tcp", lambda self, *a, **k: connected.append(a)
    )
    with pytest.raises(netguard.NotPublicHost):
        netguard.PinningBackend().connect_tcp("evil.example", 443)
    assert connected == []


def test_pinning_backend_connects_to_the_validated_address(monkeypatch):
    from norapi import netguard

    monkeypatch.setattr(netguard, "public_address", lambda host, port: "93.184.216.34")
    seen = []
    monkeypatch.setattr(
        netguard.httpcore.SyncBackend,
        "connect_tcp",
        lambda self, host, port, *a, **k: seen.append((host, port)) or object(),
    )
    netguard.PinningBackend().connect_tcp("example.com", 443)
    assert seen == [("93.184.216.34", 443)], "socket goes to the pinned address, URL keeps the name"


def test_public_client_never_follows_redirects_on_its_own():
    from norapi.netguard import PinningTransport, public_client

    client = public_client()
    assert client.follow_redirects is False
    assert isinstance(client._transport, PinningTransport)
