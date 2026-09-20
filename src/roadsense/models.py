"""Core domain types shared by the collector, database layer and API.

Plain frozen dataclasses: no framework, no database coupling. Everything else
in the system converts to/from these.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Station:
    id: int
    name: str
    lat: float
    lon: float
    municipality: str | None = None
    province: str | None = None


@dataclass(frozen=True)
class Observation:
    """One station's readings at one point in time.

    Every measurement is optional: stations differ in installed sensors, and
    a sensor can be missing from a payload. Absent != zero, so we keep None.
    """

    station_id: int
    measured_at: datetime
    air_temp_c: float | None = None
    road_temp_c: float | None = None
    road_condition_code: int | None = None  # KELI_1 numeric code
    road_condition: str | None = None  # KELI_1 English description, e.g. "Dry"
    friction: float | None = None  # KITKA1, coefficient of friction (0.82 dry ... ~0.3 icy)
    precipitation_mm_h: float | None = None
    visibility_m: float | None = None
    wind_avg_ms: float | None = None
    warning_code: int | None = None  # VAROITUS_1, 0 = OK
