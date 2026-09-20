"""Collector command line.

    python -m roadsense.collector seed              # once: station metadata + province
    python -m roadsense.collector collect           # every N minutes (scheduled job)
    python -m roadsense.collector collect --dry-run # no cloud: fetch + parse only

Run-once shape on purpose: in Azure a cron trigger starts this process and it
exits when done. Exit code != 0 marks the run as failed for the scheduler.
"""

import argparse
import logging
import sys

from roadsense.collector.digitraffic import DigitrafficClient, DigitrafficError
from roadsense.collector.run import collect_once, seed_stations
from roadsense.config import get_settings
from roadsense.db import get_repository
from roadsense.db.repository import InMemoryRepository
from roadsense.logging_setup import configure_logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="roadsense.collector")
    parser.add_argument("command", choices=["seed", "collect"])
    parser.add_argument("--dry-run", action="store_true", help="do not write to the database")
    args = parser.parse_args(argv)

    settings = get_settings()
    configure_logging(settings.log_level)
    log = logging.getLogger("roadsense.collector")

    repo = InMemoryRepository() if args.dry_run else get_repository(settings)
    if not args.dry_run and isinstance(repo, InMemoryRepository):
        # Fail loudly: a scheduled run that silently stores nothing is worse than a crash.
        log.error("COSMOS_ENDPOINT / COSMOS_KEY not set (use --dry-run to run without a database)")
        return 2

    try:
        with DigitrafficClient(settings.digitraffic_base_url, settings.digitraffic_user) as client:
            if args.command == "seed":
                seed_stations(client, repo)
            else:
                collect_once(client, repo)
    except DigitrafficError:
        log.exception("%s failed", args.command)
        return 1

    if args.dry_run:
        for status in repo.list_latest()[:5]:
            log.info("dry-run sample: %s", status.latest)
    return 0


if __name__ == "__main__":
    sys.exit(main())
