"""Run the collector once: fetch the bulk payload and parse it.

    python -m roadsense.collector

Step 3 will add "store to database". Keeping the run-once shape is deliberate:
in the cloud a scheduler starts this process every N minutes and it exits when done.
"""

import logging
import sys

from roadsense.collector.digitraffic import DigitrafficClient, DigitrafficError
from roadsense.collector.parser import parse_all_data
from roadsense.config import get_settings


def main() -> int:
    settings = get_settings()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    log = logging.getLogger("roadsense.collector")

    try:
        with DigitrafficClient(settings.digitraffic_base_url, settings.digitraffic_user) as client:
            payload = client.fetch_all_data()
    except DigitrafficError:
        log.exception("collection failed")
        return 1  # non-zero exit code: the scheduler/CI will see this run as failed

    observations = parse_all_data(payload)
    for obs in observations[:5]:
        log.info(
            "station=%s at=%s air=%s°C road=%s°C condition=%s friction=%s",
            obs.station_id,
            obs.measured_at,
            obs.air_temp_c,
            obs.road_temp_c,
            obs.road_condition,
            obs.friction,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
