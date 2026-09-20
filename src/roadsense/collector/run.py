"""Collector use-cases, independent of CLI and of the storage backend.

Keeping these as plain functions taking a Repository lets tests drive them with
InMemoryRepository and a fake Digitraffic client.
"""

import logging

from roadsense.collector.digitraffic import DigitrafficClient
from roadsense.collector.parser import (
    parse_all_data,
    parse_station_detail,
    parse_station_feature,
)
from roadsense.db.repository import Repository

log = logging.getLogger(__name__)


def seed_stations(client: DigitrafficClient, repo: Repository) -> int:
    """One-off: fetch every station + its province and store the metadata.

    Province only exists on the per-station detail endpoint, so this makes ~530
    requests. That is why it is a separate command and not part of every collection.
    """
    stations = []
    for feature in client.fetch_stations():
        base = parse_station_feature(feature)
        detail = client.fetch_station_detail(base.id)
        stations.append(parse_station_detail(detail, base))
    n = repo.upsert_stations(stations)
    log.info("seeded %d stations", n)
    return n


def collect_once(client: DigitrafficClient, repo: Repository) -> int:
    """Scheduled job: one bulk fetch, parse, store. Idempotent - safe to re-run."""
    payload = client.fetch_all_data()
    observations = parse_all_data(payload)
    n = repo.save_observations(observations)
    log.info("stored %d observations", n)
    return n
