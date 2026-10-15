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
    """Fetcher tests use made-up hosts behind a mock transport; treat them as public."""
    from norapi import netguard

    original = netguard.public_address

    def resolve(host: str, port: int):
        if host in ("x.no", "feed.test"):
            return host
        return original(host, port)

    monkeypatch.setattr(netguard, "public_address", resolve)
