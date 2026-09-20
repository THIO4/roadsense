"""API tests: FastAPI TestClient + InMemoryRepository injected via dependency override.

No server process, no network, no Cosmos - yet the full HTTP layer (routing, validation,
serialisation, status codes) is exercised.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from roadsense.api.app import app, get_repo
from roadsense.db.repository import InMemoryRepository
from roadsense.models import Observation, Station


@pytest.fixture
def client():
    repo = InMemoryRepository()
    repo.upsert_stations(
        [
            Station(
                id=1, name="vt1_Espoo", lat=60.2, lon=24.6, municipality="Espoo", province="Uusimaa"
            ),
            Station(
                id=2,
                name="vt4_Oulu",
                lat=65.0,
                lon=25.5,
                municipality="Oulu",
                province="Pohjois-Pohjanmaa",
            ),
        ]
    )
    repo.save_observations(
        [
            Observation(
                station_id=1,
                measured_at=datetime(2026, 1, 15, 7, tzinfo=UTC),
                road_condition_code=7,
                road_condition="Ice",
                road_temp_c=-4.0,
            )
        ]
    )
    app.dependency_overrides[get_repo] = lambda: repo
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_provinces(client):
    assert client.get("/provinces").json() == ["Pohjois-Pohjanmaa", "Uusimaa"]


def test_stations_filter(client):
    assert [s["id"] for s in client.get("/stations", params={"province": "Uusimaa"}).json()] == [1]
    assert len(client.get("/stations").json()) == 2


def test_conditions_with_index(client):
    body = client.get("/conditions", params={"province": "Uusimaa"}).json()
    assert body["station_count"] == 1
    [item] = body["stations"]
    assert item["latest"]["road_condition"] == "Ice"
    assert item["index"]["score"] == 35  # Ice 55 + near_freezing 10
    assert item["index"]["band"] == "hazardous"
    assert [f["name"] for f in item["index"]["factors"]] == ["road_condition", "near_freezing"]
    assert body["average_score"] == 35.0


def test_conditions_station_without_data_is_unknown(client):
    body = client.get("/conditions", params={"province": "Pohjois-Pohjanmaa"}).json()
    [item] = body["stations"]
    assert item["latest"] is None
    assert item["index"] == {"score": None, "band": "unknown", "factors": []}
    assert body["average_score"] is None


def test_unknown_province_is_404(client):
    assert client.get("/conditions", params={"province": "Atlantis"}).status_code == 404


def test_frontend_is_served(client):
    r = client.get("/")
    assert r.status_code == 200 and "RoadSense Finland" in r.text
    assert client.get("/static/app.js").status_code == 200
