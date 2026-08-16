import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


def _load(name):
    return json.loads((FIXTURES / name).read_text())


@pytest.fixture
def search_props():
    return _load("search_watches.json")


@pytest.fixture
def lot_open_props():
    return _load("lot_open.json")


@pytest.fixture
def lot_closed_props():
    return _load("lot_closed.json")
