from norapi.check import _unverifiable
from norapi.model import ApiEntry, Provider


def _entry(auth: str, probe_url: str | None = None) -> ApiEntry:
    return ApiEntry(id="e", title="E", provider=Provider(name="P"), auth=auth, probe_url=probe_url)


def test_a_404_on_a_login_only_base_url_is_not_evidence():
    assert _unverifiable(_entry("maskinporten"), {"status": 404})
    assert not _unverifiable(_entry("none"), {"status": 404}), "an open API should answer"
    assert not _unverifiable(_entry("maskinporten", "https://x.no/health"), {"status": 404})
    assert not _unverifiable(_entry("maskinporten"), {"status": None}), "a dead host still counts"
    assert not _unverifiable(_entry("maskinporten"), {"status": 401})
