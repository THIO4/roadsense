"""Thin HTTP client for the Digitraffic road weather API.

Knows only about HTTP: endpoints, headers, timeouts, retries. Returns raw JSON
dicts; converting them into domain objects is parser.py's job.

API docs: https://www.digitraffic.fi/en/road-traffic/  (weather v1 endpoints)
"""

import logging
from typing import Any

import httpx

log = logging.getLogger(__name__)

STATIONS_PATH = "/api/weather/v1/stations"
STATION_DETAIL_PATH = "/api/weather/v1/stations/{station_id}"
ALL_DATA_PATH = "/api/weather/v1/stations/data"


class DigitrafficError(Exception):
    """Raised when Digitraffic cannot be reached or answers with an error."""


class DigitrafficClient:
    def __init__(
        self,
        base_url: str,
        user_agent: str,
        *,
        timeout_s: float = 20.0,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        # Digitraffic asks every client to identify itself with the Digitraffic-User header.
        # gzip is negotiated automatically by httpx (the bulk payload is ~360 KB compressed).
        self._client = httpx.Client(
            base_url=base_url,
            headers={"Digitraffic-User": user_agent, "Accept": "application/json"},
            timeout=timeout_s,
            # retries=3 covers *connection-level* failures (DNS, refused, reset), not HTTP 5xx.
            # `transport` is injectable so tests can substitute a fake server.
            transport=transport or httpx.HTTPTransport(retries=3),
        )

    def _get(self, path: str) -> Any:
        try:
            resp = self._client.get(path)
            resp.raise_for_status()  # turns 4xx/5xx into an exception
            return resp.json()
        except httpx.HTTPError as exc:
            # Wrap the library exception so callers depend on *our* error type, not httpx's.
            raise DigitrafficError(f"GET {path} failed: {exc}") from exc

    def fetch_stations(self) -> list[dict[str, Any]]:
        """All weather stations as GeoJSON features (id, name, coordinates)."""
        return self._get(STATIONS_PATH)["features"]

    def fetch_station_detail(self, station_id: int) -> dict[str, Any]:
        """Metadata for one station, incl. municipality and province."""
        return self._get(STATION_DETAIL_PATH.format(station_id=station_id))["properties"]

    def fetch_all_data(self) -> dict[str, Any]:
        """Latest sensor values for *every* station in a single request."""
        return self._get(ALL_DATA_PATH)

    def close(self) -> None:
        self._client.close()

    # Allow `with DigitrafficClient(...) as c:` so the connection pool is always released.
    def __enter__(self) -> "DigitrafficClient":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()
