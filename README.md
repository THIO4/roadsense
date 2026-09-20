# RoadSense Finland

Cloud Engineering course project (Assignment 2: advanced pipeline with cloud client,
CI/CD basics, containerization).

RoadSense collects Finnish road weather observations from the open
[Digitraffic API](https://www.digitraffic.fi/en/road-traffic/), stores them in a cloud
database, computes a simple **educational** driving conditions index, and shows the result
in a web UI. The index is our own transparent metric for learning purposes - it is **not**
an official safety rating.

## Architecture

```text
Digitraffic API -> Azure Container Apps Job (collector, cron) -> Azure Cosmos DB
                -> Azure Container App (FastAPI + static frontend) -> browser
GitHub -> GitHub Actions (ruff + pytest -> docker build -> GHCR -> az containerapp update)
```

See `docs/` for architecture decisions, the assignment-concept mapping and cleanup steps.

## Local development

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env

ruff check . && pytest          # lint + tests (same as CI)
python -m roadsense.collector collect --dry-run   # fetch + parse, no database
python -m roadsense.collector seed                # once: station metadata -> Cosmos
python -m roadsense.collector collect             # observations -> Cosmos
uvicorn roadsense.api.app:app --reload            # API at http://127.0.0.1:8000/docs
```

## Project layout

```text
src/roadsense/
  config.py            settings from environment variables (pydantic-settings)
  models.py            Station / Observation dataclasses shared by all layers
  collector/
    digitraffic.py     HTTP client (httpx) - only knows URLs/headers/errors
    parser.py          raw JSON -> domain objects (pure, fixture-tested)
    run.py             seed_stations / collect_once use-cases
    __main__.py        CLI: seed | collect [--dry-run]
  db/
    repository.py      Repository interface + InMemoryRepository (tests, dry-run)
    cosmos.py          Azure Cosmos DB implementation (the cloud client)
  index.py             driving conditions index (docs/index.md)
  api/
    app.py             FastAPI endpoints: /health /provinces /stations /conditions
    schemas.py         response models (public API contract)
  static/              frontend: index.html, app.js, style.css (served at /)
infra/                 azure-setup.sh - creates the cloud resources with the az CLI
tests/                 pytest; fixtures/ holds real API samples so tests never hit the network
docs/                  decisions, assignment mapping, cleanup checklist
```
