import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures() -> Path:
    return FIXTURES


@pytest.fixture
def snapshot() -> dict:
    return json.loads((FIXTURES / "fdk_snapshot.json").read_text(encoding="utf-8"))


@pytest.fixture(autouse=True)
def allow_test_hosts(monkeypatch):
    """Fetcher tests use made-up hosts behind a mock transport; pin them to themselves."""
    from urllib.parse import urlparse

    from norapi import netguard

    original = netguard.resolve_public

    def resolve(url: str):
        if url.startswith(("https://x.no/", "https://x.no?", "https://feed.test/")):
            host = urlparse(url).hostname
            return netguard.PinnedTarget(host=host, port=443, connect_host=host)
        return original(url)

    monkeypatch.setattr(netguard, "resolve_public", resolve)
