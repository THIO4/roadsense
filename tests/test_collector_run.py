"""End-to-end collector logic with a fake Digitraffic server and in-memory storage."""

import httpx

from roadsense.collector.digitraffic import DigitrafficClient
from roadsense.collector.run import collect_once, seed_stations
from roadsense.db.repository import InMemoryRepository


def fake_digitraffic(stations_payload, stations_data_payload) -> DigitrafficClient:
    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if path == "/api/weather/v1/stations":
            return httpx.Response(200, json=stations_payload)
        if path == "/api/weather/v1/stations/data":
            return httpx.Response(200, json=stations_data_payload)
        if path.startswith("/api/weather/v1/stations/"):
            sid = path.rsplit("/", 1)[-1]
            return httpx.Response(
                200,
                json={
                    "properties": {"id": int(sid), "municipality": "Espoo", "province": "Uusimaa"}
                },
            )
        return httpx.Response(404)

    return DigitrafficClient("https://example.test", "test", transport=httpx.MockTransport(handler))


def test_seed_then_collect(stations_payload, stations_data_payload):
    repo = InMemoryRepository()
    with fake_digitraffic(stations_payload, stations_data_payload) as client:
        assert seed_stations(client, repo) == 2
        assert collect_once(client, repo) == 2  # fixture: 3 stations, one without data

    statuses = repo.list_latest("Uusimaa")
    assert {s.station.id for s in statuses} == {1001, 1002}
    assert all(s.latest is not None for s in statuses)


def test_collect_is_idempotent(stations_payload, stations_data_payload):
    repo = InMemoryRepository()
    with fake_digitraffic(stations_payload, stations_data_payload) as client:
        seed_stations(client, repo)
        collect_once(client, repo)
        collect_once(client, repo)  # same data again
    # latest is unchanged; history grows in memory but Cosmos dedupes by document id
    [espoo] = [s for s in repo.list_latest() if s.station.id == 1001]
    assert espoo.latest is not None and espoo.latest.air_temp_c == 14.9
