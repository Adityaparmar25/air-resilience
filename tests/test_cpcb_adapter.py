"""Tests for CPCB Ingestion Adapter."""

import pytest
from datetime import datetime, timezone
from services.ingestion.cpcb_adapter import CPCBAdapter


def test_cpcb_adapter_field_translation():
    """Test translating typical CPCB columns to canonical schema."""
    adapter = CPCBAdapter()
    raw_record = {
        "StationId": "DL001",
        "StationName": "Anand Vihar, Delhi",
        "Date": "2026-01-15 14:00:00",
        "Latitude": 28.6508,
        "Longitude": 77.3152,
        "City": "Delhi",
        "State": "Delhi",
        "PM2.5 (ug/m3)": "178.4",
        "PM10 (ug/m3)": "310.2",
        "NO2 (ug/m3)": "55.0",
        "SO2 (ug/m3)": "14.5",
        "CO (mg/m3)": "2.1",
        "Ozone (ug/m3)": "28.0",
    }

    obs, meta = adapter.normalize(raw_record, is_fixture=True)

    assert obs.station_id == "DL001"
    assert obs.pm25 == 178.4
    assert obs.pm10 == 310.2
    assert obs.no2 == 55.0
    assert obs.so2 == 14.5
    assert obs.co == 2.1
    assert obs.o3 == 28.0
    assert obs.lat == 28.6508
    assert obs.lon == 77.3152
    assert meta["data_source"] == "fixture"
    assert meta["raw_payload"] == raw_record


def test_cpcb_adapter_handles_na_and_missing_pollutants():
    """Missing and 'NA' values must translate to None, never 0.0."""
    adapter = CPCBAdapter()
    raw_record = {
        "StationId": "DL001",
        "StationName": "Anand Vihar",
        "Date": "2026-01-15 15:00:00",
        "PM2.5": "NA",
        "PM10": "-",
        "NO2": "None",
        "CO": "",
        # SO2, O3 not present in record
    }

    obs, _ = adapter.normalize(raw_record, is_fixture=True)

    assert obs.pm25 is None
    assert obs.pm10 is None
    assert obs.no2 is None
    assert obs.so2 is None
    assert obs.co is None
    assert obs.o3 is None


def test_cpcb_adapter_station_registry_fallback():
    """Known station ID fills in lat/lon/city/state if omitted in raw record."""
    adapter = CPCBAdapter()
    raw_record = {
        "station_id": "UP001",
        "timestamp": "2026-01-15T12:00:00Z",
        "pm25": 120.0,
    }

    obs, _ = adapter.normalize(raw_record, is_fixture=True)

    assert obs.station_id == "UP001"
    assert obs.station_name == "Sector 62, Noida"
    assert obs.city == "Noida"
    assert obs.state == "Uttar Pradesh"
    assert obs.lat == 28.6245
    assert obs.lon == 77.3639
    assert obs.pm25 == 120.0


def test_cpcb_adapter_invalid_record_rejection():
    """Missing essential identification fields must raise ValueError."""
    adapter = CPCBAdapter()
    with pytest.raises(ValueError, match="Missing station identifier"):
        adapter.normalize({"timestamp": "2026-01-15 10:00:00", "pm25": 50.0})

    with pytest.raises(ValueError, match="Missing timestamp field"):
        adapter.normalize({"StationId": "DL001", "pm25": 50.0})
