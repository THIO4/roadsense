"""Pydantic response models = the API's public contract.

Kept separate from the internal dataclasses in models.py on purpose: the API shape can
evolve (or hide fields) without touching storage code. FastAPI uses these for validation,
JSON serialisation and the OpenAPI docs at /docs.
"""

from datetime import datetime

from pydantic import BaseModel

from roadsense.index import IndexResult
from roadsense.models import Observation, Station


class StationOut(BaseModel):
    id: int
    name: str
    lat: float
    lon: float
    municipality: str | None
    province: str | None

    @classmethod
    def from_model(cls, s: Station) -> "StationOut":
        return cls(**s.__dict__)


class ObservationOut(BaseModel):
    measured_at: datetime
    air_temp_c: float | None
    road_temp_c: float | None
    road_condition: str | None
    friction: float | None
    precipitation_mm_h: float | None
    visibility_m: float | None
    wind_avg_ms: float | None
    warning_code: int | None

    @classmethod
    def from_model(cls, o: Observation) -> "ObservationOut":
        return cls(**{k: getattr(o, k) for k in cls.model_fields})


class FactorOut(BaseModel):
    name: str
    penalty: int
    detail: str


class IndexOut(BaseModel):
    score: int | None
    band: str
    factors: list[FactorOut]

    @classmethod
    def from_model(cls, r: IndexResult) -> "IndexOut":
        return cls(score=r.score, band=r.band, factors=[FactorOut(**f.__dict__) for f in r.factors])


class ConditionsOut(BaseModel):
    """One station with its latest observation and computed index."""

    station: StationOut
    latest: ObservationOut | None
    index: IndexOut


class ConditionsSummaryOut(BaseModel):
    province: str | None
    station_count: int
    average_score: float | None
    stations: list[ConditionsOut]
