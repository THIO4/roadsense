"""Azure Cosmos DB implementation of the Repository - the project's "cloud client".

Uses the official `azure-cosmos` SDK. Every call here becomes an HTTPS request to
the Cosmos endpoint, authenticated with the account key, and costs Request Units.

Data model (see docs/decisions.md D7):
  stations      pk /id          station metadata + embedded `latest` observation
  observations  pk /station_id  history, auto-deleted by container TTL
"""

import logging
from collections.abc import Iterable
from dataclasses import asdict
from datetime import datetime
from typing import Any

from azure.cosmos import ContainerProxy, CosmosClient, exceptions

from roadsense.models import Observation, Station, StationStatus

log = logging.getLogger(__name__)

STATIONS_CONTAINER = "stations"
OBSERVATIONS_CONTAINER = "observations"


# --- (de)serialisation: dataclasses <-> JSON documents ---------------------------------
# Cosmos requires a string `id` and cannot store datetime objects, so we convert here.


def station_to_doc(station: Station) -> dict[str, Any]:
    doc = asdict(station)
    doc["id"] = str(station.id)
    return doc


def doc_to_station(doc: dict[str, Any]) -> Station:
    return Station(
        id=int(doc["id"]),
        name=doc["name"],
        lat=doc["lat"],
        lon=doc["lon"],
        municipality=doc.get("municipality"),
        province=doc.get("province"),
    )


def observation_to_doc(obs: Observation) -> dict[str, Any]:
    doc = asdict(obs)
    doc["station_id"] = str(obs.station_id)
    doc["measured_at"] = obs.measured_at.isoformat()
    # Deterministic id -> re-running the collector on unchanged data upserts the same
    # document instead of creating a duplicate (idempotent writes).
    doc["id"] = f"{obs.station_id}:{doc['measured_at']}"
    return doc


def doc_to_observation(doc: dict[str, Any]) -> Observation:
    fields = {k: doc.get(k) for k in Observation.__dataclass_fields__}
    fields["station_id"] = int(doc["station_id"])
    fields["measured_at"] = datetime.fromisoformat(doc["measured_at"])
    return Observation(**fields)


# --- repository ------------------------------------------------------------------------


class CosmosRepository:
    def __init__(self, endpoint: str, key: str, database: str) -> None:
        # One client per process: it owns an HTTP connection pool and is thread-safe.
        client = CosmosClient(endpoint, credential=key)
        # get_* does not call the service; the containers must already exist
        # (created by infra/azure-setup.sh). Keeping schema creation out of app code
        # means the app never needs management permissions - least privilege.
        db = client.get_database_client(database)
        self._stations: ContainerProxy = db.get_container_client(STATIONS_CONTAINER)
        self._observations: ContainerProxy = db.get_container_client(OBSERVATIONS_CONTAINER)

    def upsert_stations(self, stations: Iterable[Station]) -> int:
        n = 0
        for station in stations:
            # Preserve `latest` if the station already exists; upsert replaces the whole doc.
            doc = station_to_doc(station)
            try:
                existing = self._stations.read_item(item=doc["id"], partition_key=doc["id"])
                if "latest" in existing:
                    doc["latest"] = existing["latest"]
            except exceptions.CosmosResourceNotFoundError:
                pass
            self._stations.upsert_item(doc)
            n += 1
        return n

    def list_stations(self, province: str | None = None) -> list[Station]:
        return [doc_to_station(d) for d in self._query_stations(province)]

    def list_provinces(self) -> list[str]:
        # SELECT DISTINCT VALUE returns bare strings instead of {"province": ...} objects.
        query = "SELECT DISTINCT VALUE c.province FROM c WHERE IS_DEFINED(c.province)"
        return sorted(self._stations.query_items(query, enable_cross_partition_query=True))

    def save_observations(self, observations: Iterable[Observation]) -> int:
        n = 0
        for obs in observations:
            doc = observation_to_doc(obs)
            self._observations.upsert_item(doc)
            # Patch = send only the changed field, not the whole station document.
            latest = {k: v for k, v in doc.items() if k not in ("id", "station_id")}
            try:
                self._stations.patch_item(
                    item=str(obs.station_id),
                    partition_key=str(obs.station_id),
                    patch_operations=[{"op": "set", "path": "/latest", "value": latest}],
                )
            except exceptions.CosmosResourceNotFoundError:
                # Data for a station we have not seeded (new station). Not fatal.
                log.warning("station %s not in stations container; run seed", obs.station_id)
            n += 1
        return n

    def list_latest(self, province: str | None = None) -> list[StationStatus]:
        result = []
        for doc in self._query_stations(province):
            latest = doc.get("latest")
            obs = None
            if latest:
                obs = doc_to_observation({**latest, "station_id": doc["id"]})
            result.append(StationStatus(station=doc_to_station(doc), latest=obs))
        return result

    def _query_stations(self, province: str | None) -> Iterable[dict[str, Any]]:
        # Parameterised query: never format user input into the query string (injection).
        if province is None:
            query, params = "SELECT * FROM c", []
        else:
            query = "SELECT * FROM c WHERE c.province = @province"
            params = [{"name": "@province", "value": province}]
        # Partition key is /id, so filtering by province spans all partitions.
        # With ~530 small documents this costs a few RU - acceptable (decision D7).
        return self._stations.query_items(
            query, parameters=params, enable_cross_partition_query=True
        )
