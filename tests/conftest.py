"""Shared pytest fixtures. Anything defined here is available to every test file."""

import json
from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def stations_data_payload() -> dict:
    """A trimmed, real /stations/data response saved on 2026-09-20."""
    return json.loads((FIXTURES / "stations_data.json").read_text(encoding="utf-8"))


@pytest.fixture
def stations_payload() -> dict:
    """A trimmed, real /stations response."""
    return json.loads((FIXTURES / "stations.json").read_text(encoding="utf-8"))
