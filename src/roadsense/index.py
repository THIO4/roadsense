"""RoadSense driving conditions index - an EDUCATIONAL metric, not an official safety rating.

Score = 100 minus documented penalties, clamped to 0..100. Every applied penalty is
returned as a named Factor so the result can always be explained ("why 45?").

Design rules
  * Surface state is measured two ways (road condition code, friction). They describe the
    same thing, so we apply the *larger* of the two penalties, not both (no double counting).
  * Missing sensors never penalise: absent is not the same as bad. If *no* surface
    information exists at all, the index is None ("insufficient data").
  * Thresholds are round, defensible numbers (see docs/index.md), not tuned to any dataset.
"""

from dataclasses import dataclass

from roadsense.models import Observation

# KELI_1 codes from https://tie.digitraffic.fi/api/weather/v1/sensors (0 = sensor fault)
ROAD_CONDITION_PENALTY: dict[int, int] = {
    1: 0,  # Dry
    2: 5,  # Moist
    3: 10,  # Wet
    4: 10,  # Wet and salty
    8: 5,  # Probably moist and salty
    9: 30,  # Slushy
    5: 40,  # Frost
    6: 40,  # Snow
    7: 55,  # Ice
}

# VAROITUS_1 station warning codes
WARNING_PENALTY: dict[int, int] = {1: 10, 2: 20, 3: 15, 4: 5}  # Beware, Alarm, Frost, Rain

BANDS: list[tuple[int, str]] = [(80, "good"), (60, "fair"), (40, "poor"), (0, "hazardous")]


@dataclass(frozen=True)
class Factor:
    name: str
    penalty: int
    detail: str


@dataclass(frozen=True)
class IndexResult:
    score: int | None  # None = insufficient data
    band: str
    factors: tuple[Factor, ...]


def band_for(score: int) -> str:
    for threshold, name in BANDS:
        if score >= threshold:
            return name
    return "hazardous"


def _surface_factor(obs: Observation) -> Factor | None:
    """Larger of road-condition-code and friction penalties (they measure the same thing)."""
    candidates: list[Factor] = []
    code = obs.road_condition_code
    if code is not None and code in ROAD_CONDITION_PENALTY:
        p = ROAD_CONDITION_PENALTY[code]
        candidates.append(Factor("road_condition", p, obs.road_condition or f"code {code}"))
    if obs.friction is not None:
        mu = obs.friction
        # Rough physical bands: dry asphalt ~0.8, wet ~0.5-0.6, snow ~0.3, ice <0.2
        p = 0 if mu >= 0.6 else 15 if mu >= 0.45 else 30 if mu >= 0.3 else 50
        candidates.append(Factor("friction", p, f"µ={mu:.2f}"))
    if not candidates:
        return None
    return max(candidates, key=lambda f: f.penalty)


def compute_index(obs: Observation) -> IndexResult:
    surface = _surface_factor(obs)
    if surface is None:
        return IndexResult(score=None, band="unknown", factors=())

    factors: list[Factor] = [surface]

    # Ice risk: road at/below freezing AND something to freeze (moisture or precipitation).
    if obs.road_temp_c is not None and obs.road_temp_c <= 1.0:
        wet = (obs.road_condition_code or 0) in (2, 3, 4, 8) or (obs.precipitation_mm_h or 0) > 0
        if wet:
            factors.append(Factor("ice_risk", 20, f"road {obs.road_temp_c:.1f}°C with moisture"))
        else:
            factors.append(Factor("near_freezing", 10, f"road {obs.road_temp_c:.1f}°C"))

    if obs.precipitation_mm_h is not None and obs.precipitation_mm_h > 0.5:
        mm = obs.precipitation_mm_h
        p = 25 if mm > 5 else 15 if mm > 2 else 5
        factors.append(Factor("precipitation", p, f"{mm:.1f} mm/h"))

    if obs.visibility_m is not None and obs.visibility_m < 1000:
        v = obs.visibility_m
        p = 30 if v < 200 else 20 if v < 500 else 10
        factors.append(Factor("visibility", p, f"{v:.0f} m"))

    if obs.wind_avg_ms is not None and obs.wind_avg_ms > 12:
        w = obs.wind_avg_ms
        factors.append(Factor("wind", 20 if w > 17 else 10, f"{w:.1f} m/s"))

    if obs.warning_code in WARNING_PENALTY:
        factors.append(
            Factor("station_warning", WARNING_PENALTY[obs.warning_code], f"code {obs.warning_code}")
        )

    # Only report factors that actually cost points - keeps the explanation short.
    applied = tuple(f for f in factors if f.penalty > 0)
    score = max(0, min(100, 100 - sum(f.penalty for f in applied)))
    return IndexResult(score=score, band=band_for(score), factors=applied)
