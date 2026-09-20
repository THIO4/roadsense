"""Repository contract tests, run against InMemoryRepository.

The Cosmos implementation is exercised by tests/test_cosmos_integration.py when
credentials are available; the contract (what a Repository must do) is defined here.
"""

from datetime import UTC, datetime

from roadsense.db.repository import InMemoryRepository
from roadsense.models import Observation, Station

ESPOO = Station(
    id=1, name="vt1_Espoo", lat=60.2, lon=24.6, municipality="Espoo", province="Uusimaa"
)
OULU = Station(
    id=2, name="vt4_Oulu", lat=65.0, lon=25.5, municipality="Oulu", province="Pohjois-Pohjanmaa"
)


def obs(station_id: int, hour: int, temp: float) -> Observation:
    return Observation(
        station_id=station_id, measured_at=datetime(2026, 9, 20, hour, tzinfo=UTC), air_temp_c=temp
    )


def test_upsert_stations_replaces_existing():
    repo = InMemoryRepository()
    repo.upsert_stations([ESPOO])
    repo.upsert_stations([Station(id=1, name="renamed", lat=60.2, lon=24.6, province="Uusimaa")])
    assert [s.name for s in repo.list_stations()] == ["renamed"]


def test_list_stations_filters_by_province():
    repo = InMemoryRepository()
    repo.upsert_stations([ESPOO, OULU])
    assert [s.id for s in repo.list_stations("Uusimaa")] == [1]
    assert repo.list_provinces() == ["Pohjois-Pohjanmaa", "Uusimaa"]


def test_latest_keeps_newest_observation():
    repo = InMemoryRepository()
    repo.upsert_stations([ESPOO])
    repo.save_observations([obs(1, 10, 5.0), obs(1, 12, 7.0), obs(1, 11, 6.0)])  # out of order
    [status] = repo.list_latest("Uusimaa")
    assert status.latest is not None
    assert status.latest.air_temp_c == 7.0
    assert len(repo.history) == 3


def test_latest_is_none_before_any_observation():
    repo = InMemoryRepository()
    repo.upsert_stations([OULU])
    [status] = repo.list_latest()
    assert status.station == OULU
    assert status.latest is None
