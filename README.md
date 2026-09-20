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
python -m roadsense.collector   # fetch + parse live Digitraffic data once
```

## Project layout

```text
src/roadsense/
  config.py            settings from environment variables (pydantic-settings)
  models.py            Station / Observation dataclasses shared by all layers
  collector/
    digitraffic.py     HTTP client (httpx) - only knows URLs/headers/errors
    parser.py          raw JSON -> domain objects (pure, fixture-tested)
    __main__.py        run-once entry point for the scheduled job
tests/                 pytest; fixtures/ holds real API samples so tests never hit the network
docs/                  decisions, assignment mapping, cleanup checklist
```
