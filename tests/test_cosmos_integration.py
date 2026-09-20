"""Integration test against a real Cosmos DB account.

Skipped unless COSMOS_ENDPOINT and COSMOS_KEY are set, so the normal test run
(and CI) stays offline and secret-free. Run locally with a .env in place:

    pytest tests/test_cosmos_integration.py -v
"""

import os
import uuid
from datetime import UTC, datetime

import pytest

from roadsense.config import Settings
from roadsense.models import Observation, Station

pytestmark = pytest.mark.skipif(
    not (os.getenv("COSMOS_ENDPOINT") and os.getenv("COSMOS_KEY")),
    reason="Cosmos credentials not configured",
)


def test_round_trip():
    from roadsense.db.cosmos import CosmosRepository

    s = Settings()
    repo = CosmosRepository(s.cosmos_endpoint, s.cosmos_key.get_secret_value(), s.cosmos_database)  # type: ignore[union-attr]

    # Negative id + random name: cannot collide with real Digitraffic stations.
    station = Station(id=-1, name=f"test-{uuid.uuid4()}", lat=0, lon=0, province="TestProvince")
    repo.upsert_stations([station])
    repo.save_observations(
        [Observation(station_id=-1, measured_at=datetime.now(UTC), air_temp_c=1.5)]
    )

    [status] = repo.list_latest("TestProvince")
    assert status.station.name == station.name
    assert status.latest is not None and status.latest.air_temp_c == 1.5
