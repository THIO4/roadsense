"""Client tests use httpx.MockTransport: a fake server inside the test process.

No network, no Digitraffic dependency, runs in milliseconds - which is what
makes it safe to run on every push in CI.
"""

import httpx
import pytest

from roadsense.collector.digitraffic import DigitrafficClient, DigitrafficError


def make_client(handler) -> DigitrafficClient:
    return DigitrafficClient(
        "https://example.test", "test-agent", transport=httpx.MockTransport(handler)
    )


def test_sends_digitraffic_user_header(stations_data_payload):
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["headers"] = request.headers
        seen["url"] = str(request.url)
        return httpx.Response(200, json=stations_data_payload)

    with make_client(handler) as client:
        payload = client.fetch_all_data()

    assert seen["url"] == "https://example.test/api/weather/v1/stations/data"
    assert seen["headers"]["Digitraffic-User"] == "test-agent"
    assert len(payload["stations"]) == 3


def test_http_error_is_wrapped():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, text="maintenance")

    with make_client(handler) as client, pytest.raises(DigitrafficError, match="503"):
        client.fetch_all_data()


def test_fetch_stations_returns_features(stations_payload):
    with make_client(lambda r: httpx.Response(200, json=stations_payload)) as client:
        features = client.fetch_stations()
    assert features[0]["properties"]["id"] == 1001
