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
