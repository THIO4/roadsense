from datetime import UTC, datetime

from roadsense.collector.parser import (
    parse_all_data,
    parse_station_data,
    parse_station_detail,
    parse_station_feature,
)


def test_parse_station_data_maps_selected_sensors(stations_data_payload):
    obs = parse_station_data(stations_data_payload["stations"][0])

    assert obs is not None
    assert obs.station_id == 1001
    assert obs.measured_at == datetime(2026, 9, 20, 13, 55, 49, tzinfo=UTC)
    assert obs.air_temp_c == 14.9
    assert obs.road_temp_c == 18.5
    assert obs.road_condition_code == 1
    assert obs.road_condition == "Dry"
    assert obs.warning_code == 0
    assert obs.friction == 0.82


def test_parse_station_data_ignores_unlisted_sensors(stations_data_payload):
    # The fixture deliberately contains MAA_1 (ground temperature), which we don't store.
    obs = parse_station_data(stations_data_payload["stations"][0])
    assert not hasattr(obs, "MAA_1")
    assert "MAA_1" not in obs.__dict__


def test_parse_station_data_returns_none_without_sensors():
    assert parse_station_data({"id": 1, "dataUpdatedTime": "2026-01-01T00:00:00Z"}) is None
    assert (
        parse_station_data({"id": 1, "dataUpdatedTime": "2026-01-01T00:00:00Z", "sensorValues": []})
        is None
    )


def test_parse_station_data_missing_sensor_becomes_none():
    entry = {
        "id": 42,
        "dataUpdatedTime": "2026-01-01T00:00:00Z",
        "sensorValues": [{"name": "ILMA", "value": -3.0}],
    }
    obs = parse_station_data(entry)
    assert obs is not None
    assert obs.air_temp_c == -3.0
    assert obs.road_temp_c is None  # absent, not zero
    assert obs.friction is None


def test_parse_all_data_skips_empty_stations(stations_data_payload):
    observations = parse_all_data(stations_data_payload)
    # Fixture has 3 stations, one (id 9999) has no sensor values.
    assert [o.station_id for o in observations] == [1001, 1002]


def test_parse_station_feature_uses_geojson_lon_lat_order(stations_payload):
    station = parse_station_feature(stations_payload["features"][0])
    assert station.id == 1001
    assert station.name == "vt1_Espoo_Nupuri"
    assert station.lat == 60.228227  # Finland: lat ~60-70, lon ~20-31
    assert station.lon == 24.596399
    assert station.province is None


def test_parse_station_detail_enriches_station(stations_payload):
    base = parse_station_feature(stations_payload["features"][0])
    enriched = parse_station_detail({"municipality": "Espoo", "province": "Uusimaa"}, base)
    assert enriched.province == "Uusimaa"
    assert enriched.municipality == "Espoo"
    assert enriched.lat == base.lat
