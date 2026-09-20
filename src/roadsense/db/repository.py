"""Storage interface for RoadSense.

The rest of the app (collector, API) talks to a `Repository` and does not care
whether it is Cosmos DB or a dict. Benefits:
  * unit tests run against InMemoryRepository - fast, no cloud, no secrets;
  * the cloud-specific code is isolated in one module (cosmos.py);
  * swapping databases later would touch one file.
"""

from collections.abc import Iterable
from typing import Protocol

from roadsense.models import Observation, Station, StationStatus


class Repository(Protocol):
    def upsert_stations(self, stations: Iterable[Station]) -> int:
        """Insert or update station metadata. Returns number written."""
        ...

    def list_stations(self, province: str | None = None) -> list[Station]: ...

    def list_provinces(self) -> list[str]: ...

    def save_observations(self, observations: Iterable[Observation]) -> int:
        """Store observations (history) and update each station's `latest`. Returns count."""
        ...

    def list_latest(self, province: str | None = None) -> list[StationStatus]:
        """Stations (optionally filtered by province) with their most recent observation."""
        ...


class InMemoryRepository:
    """Dict-backed Repository for tests and --dry-run. Same semantics as Cosmos."""

    def __init__(self) -> None:
        self._stations: dict[int, Station] = {}
        self._latest: dict[int, Observation] = {}
        self.history: list[Observation] = []

    def upsert_stations(self, stations: Iterable[Station]) -> int:
        n = 0
        for s in stations:
            self._stations[s.id] = s
            n += 1
        return n

    def list_stations(self, province: str | None = None) -> list[Station]:
        return [s for s in self._stations.values() if province is None or s.province == province]

    def list_provinces(self) -> list[str]:
        return sorted({s.province for s in self._stations.values() if s.province})

    def save_observations(self, observations: Iterable[Observation]) -> int:
        n = 0
        for obs in observations:
            self.history.append(obs)
            current = self._latest.get(obs.station_id)
            if current is None or obs.measured_at >= current.measured_at:
                self._latest[obs.station_id] = obs
            n += 1
        return n

    def list_latest(self, province: str | None = None) -> list[StationStatus]:
        return [
            StationStatus(station=s, latest=self._latest.get(s.id))
            for s in self.list_stations(province)
        ]
