"""Convert raw Digitraffic JSON into domain objects.

Pure functions, no I/O - so they are trivially unit-testable with saved fixtures.
"""

import logging
from datetime import datetime
from typing import Any

from roadsense.models import Observation, Station

log = logging.getLogger(__name__)

# Digitraffic sensor name -> Observation field. Everything not listed is dropped:
# a station reports ~95 sensors, most are diagnostics we never use.
# See docs/decisions.md for why these eight.
SENSOR_FIELDS: dict[str, str] = {
    "ILMA": "air_temp_c",
    "TIE_1": "road_temp_c",
    "KITKA1": "friction",
    "SADE_INTENSITEETTI": "precipitation_mm_h",
    "NÄKYVYYS_M": "visibility_m",
    "KESKITUULI": "wind_avg_ms",
}
# Code-type sensors: numeric value is a category, and Digitraffic ships an English label.
ROAD_CONDITION_SENSOR = "KELI_1"
WARNING_SENSOR = "VAROITUS_1"


def parse_timestamp(value: str) -> datetime:
    # Digitraffic uses ISO-8601 with a trailing "Z"; fromisoformat handles it on 3.11+.
    return datetime.fromisoformat(value)


def parse_station_feature(feature: dict[str, Any]) -> Station:
    """GeoJSON feature from /stations -> Station (without municipality/province)."""
    props = feature["properties"]
    lon, lat = feature["geometry"]["coordinates"][:2]  # GeoJSON order is [lon, lat]
    return Station(id=int(props["id"]), name=props["name"], lat=lat, lon=lon)


def parse_station_detail(properties: dict[str, Any], base: Station) -> Station:
    """Enrich a Station with municipality/province from /stations/{id}."""
    return Station(
        id=base.id,
        name=base.name,
        lat=base.lat,
        lon=base.lon,
        municipality=properties.get("municipality"),
        province=properties.get("province"),
    )


def parse_station_data(entry: dict[str, Any]) -> Observation | None:
    """One element of the bulk /stations/data payload -> Observation.

    Returns None when the station has no sensor values (e.g. under maintenance),
    so the caller can simply skip it.
    """
    sensors = entry.get("sensorValues") or []
    if not sensors:
        return None

    fields: dict[str, Any] = {}
    for sensor in sensors:
        name = sensor.get("name")
        value = sensor.get("value")
        if value is None:
            continue
        if name in SENSOR_FIELDS:
            fields[SENSOR_FIELDS[name]] = float(value)
        elif name == ROAD_CONDITION_SENSOR:
            fields["road_condition_code"] = int(value)
            fields["road_condition"] = sensor.get("sensorValueDescriptionEn")
        elif name == WARNING_SENSOR:
            fields["warning_code"] = int(value)

    return Observation(
        station_id=int(entry["id"]),
        measured_at=parse_timestamp(entry["dataUpdatedTime"]),
        **fields,
    )


def parse_all_data(payload: dict[str, Any]) -> list[Observation]:
    """Bulk payload -> list of Observations, skipping stations without data."""
    observations: list[Observation] = []
    skipped = 0
    for entry in payload.get("stations", []):
        obs = parse_station_data(entry)
        if obs is None:
            skipped += 1
            continue
        observations.append(obs)
    log.info("parsed %d observations (%d stations without data)", len(observations), skipped)
    return observations
