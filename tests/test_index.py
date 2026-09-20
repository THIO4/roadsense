from datetime import UTC, datetime

from roadsense.index import Factor, compute_index
from roadsense.models import Observation

T = datetime(2026, 1, 15, 7, tzinfo=UTC)


def obs(**kw) -> Observation:
    return Observation(station_id=1, measured_at=T, **kw)


def names(result) -> list[str]:
    return [f.name for f in result.factors]


def test_dry_summer_road_is_100_with_no_factors():
    r = compute_index(
        obs(
            road_condition_code=1,
            road_condition="Dry",
            friction=0.82,
            air_temp_c=15,
            road_temp_c=18,
        )
    )
    assert (r.score, r.band, r.factors) == (100, "good", ())


def test_no_surface_data_gives_none():
    r = compute_index(obs(air_temp_c=-5, road_temp_c=-6))
    assert r.score is None and r.band == "unknown"


def test_sensor_fault_code_0_is_not_a_penalty_and_not_surface_data():
    r = compute_index(obs(road_condition_code=0, road_condition="The sensor has a fault"))
    assert r.score is None


def test_surface_uses_larger_of_code_and_friction_not_sum():
    # Ice (55) and friction 0.2 (50): apply 55 only.
    r = compute_index(obs(road_condition_code=7, friction=0.2))
    assert r.factors == (Factor("road_condition", 55, "code 7"),)
    assert r.score == 45 and r.band == "poor"


def test_ice_risk_needs_freezing_and_moisture():
    cold_dry = compute_index(obs(road_condition_code=1, road_temp_c=-3))
    cold_wet = compute_index(obs(road_condition_code=3, road_temp_c=-3))
    assert names(cold_dry) == ["near_freezing"] and cold_dry.score == 90
    assert names(cold_wet) == ["road_condition", "ice_risk"] and cold_wet.score == 70


def test_winter_storm_is_hazardous_and_clamped_at_zero():
    r = compute_index(
        obs(
            road_condition_code=6,
            friction=0.25,
            road_temp_c=-2,
            precipitation_mm_h=6,
            visibility_m=150,
            wind_avg_ms=18,
            warning_code=2,
        )
    )
    assert r.score == 0 and r.band == "hazardous"
    # friction 0.25 (50) outranks Snow (40) - the larger surface penalty wins
    assert names(r) == [
        "friction",
        "ice_risk",
        "precipitation",
        "visibility",
        "wind",
        "station_warning",
    ]


def test_missing_optional_sensors_do_not_penalise():
    r = compute_index(obs(road_condition_code=2))  # Moist only, everything else unknown
    assert r.score == 95 and names(r) == ["road_condition"]
