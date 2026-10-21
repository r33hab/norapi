import json

import httpx

from norapi.harvest import geonorge

UUID = "df226a30-86bf-43ee-ab11-7fd84a90ee2e"


def test_uuid_in_reads_every_kartkatalog_url_shape():
    assert geonorge.uuid_in(f"https://kartkatalog.geonorge.no/Metadata/uuid/{UUID}") == UUID
    assert geonorge.uuid_in(f"https://kartkatalog.geonorge.no/metadata/kartverket/x/{UUID}") == UUID
    assert geonorge.uuid_in(f"https://example.no/{UUID}") is None, "only kartkatalog links"
    assert geonorge.uuid_in("https://kartkatalog.geonorge.no/") is None


def test_access_of_takes_the_strictest_flag():
    assert geonorge.access_of({"AccessIsOpendata": True}) == "open"
    both = {"AccessIsOpendata": True, "AccessIsRestricted": True}
    assert geonorge.access_of(both) == "restricted"
    assert geonorge.access_of({"AccessIsProtected": True}) == "non-public"
    assert geonorge.access_of({"AccessIsOpendata": False}) is None
    assert geonorge.access_of(None) is None


def test_harvest_keeps_only_access_fields_and_skips_failures(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith(UUID):
            body = {"AccessIsOpendata": True, "DataAccess": "Åpne data", "Abstract": "lang tekst"}
            return httpx.Response(200, json=body)
        return httpx.Response(404)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    records = geonorge.harvest([UUID, "00000000-0000-0000-0000-000000000000"], tmp_path, client)

    assert set(records) == {UUID}
    assert "Abstract" not in records[UUID] and records[UUID]["DataAccess"] == "Åpne data"
    assert json.loads((tmp_path / geonorge.SNAPSHOT).read_text()) == records
    assert geonorge.load_snapshot(tmp_path) == records
    assert geonorge.load_snapshot(tmp_path / "missing") == {}
