"""FastAPI application.

    uvicorn roadsense.api.app:app --reload      # local dev, docs at http://127.0.0.1:8000/docs

Endpoints read from the Repository only; the collector writes. Keeping the API read-only
means it needs no write permissions - and a bug here can never corrupt data.
"""

import logging
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from roadsense.api.schemas import (
    ConditionsOut,
    ConditionsSummaryOut,
    IndexOut,
    ObservationOut,
    StationOut,
)
from roadsense.config import get_settings
from roadsense.db import get_repository
from roadsense.db.repository import Repository
from roadsense.index import IndexResult, compute_index
from roadsense.logging_setup import configure_logging

log = logging.getLogger(__name__)


@lru_cache
def _cached_repository() -> Repository:
    # One Repository (= one Cosmos client + connection pool) for the process lifetime.
    return get_repository(get_settings())


def get_repo() -> Iterator[Repository]:
    """FastAPI dependency. Tests override this to inject InMemoryRepository."""
    yield _cached_repository()


RepoDep = Annotated[Repository, Depends(get_repo)]

app = FastAPI(
    title="RoadSense Finland",
    version="0.1.0",
    description="Road weather observations from Digitraffic and an educational driving "
    "conditions index. Not an official safety metric.",
)
configure_logging(get_settings().log_level)

# Frontend: plain HTML/CSS/JS shipped inside the package and served by the same app.
# Same origin as the API -> no CORS configuration, one container, one URL.
STATIC_DIR = Path(__file__).resolve().parent.parent / "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness probe: Container Apps and the CI smoke test call this."""
    return {"status": "ok"}


@app.get("/provinces", response_model=list[str])
def provinces(repo: RepoDep) -> list[str]:
    return repo.list_provinces()


@app.get("/stations", response_model=list[StationOut])
def stations(repo: RepoDep, province: str | None = None) -> list[StationOut]:
    return [StationOut.from_model(s) for s in repo.list_stations(province)]


@app.get("/conditions", response_model=ConditionsSummaryOut)
def conditions(
    repo: RepoDep,
    province: Annotated[str | None, Query(description="Filter by province, e.g. Uusimaa")] = None,
) -> ConditionsSummaryOut:
    """Latest observation + driving conditions index for every station (in a province)."""
    statuses = repo.list_latest(province)
    if province is not None and not statuses:
        raise HTTPException(status_code=404, detail=f"unknown province: {province}")

    items: list[ConditionsOut] = []
    for st in statuses:
        result = (
            compute_index(st.latest)
            if st.latest
            else IndexResult(score=None, band="unknown", factors=())
        )
        items.append(
            ConditionsOut(
                station=StationOut.from_model(st.station),
                latest=ObservationOut.from_model(st.latest) if st.latest else None,
                index=IndexOut.from_model(result),
            )
        )

    scores = [i.index.score for i in items if i.index.score is not None]
    return ConditionsSummaryOut(
        province=province,
        station_count=len(items),
        average_score=round(sum(scores) / len(scores), 1) if scores else None,
        stations=items,
    )
