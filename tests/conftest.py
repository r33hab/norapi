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
    """Fetcher tests use made-up hosts behind a mock transport; let them past the SSRF guard."""
    from norapi import netguard

    original = netguard.is_public_url

    def guard(url: str) -> bool:
        return url.startswith(("https://x.no/", "https://feed.test/")) or original(url)

    monkeypatch.setattr(netguard, "is_public_url", guard)
