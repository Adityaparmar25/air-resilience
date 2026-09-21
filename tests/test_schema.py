"""Tests for canonical monitoring observation schema."""

from datetime import datetime, timezone, timedelta
import pytest
from pydantic import ValidationError
from schemas.canonical import MonitoringObservation


def test_valid_observation():
    """Test valid observation parsing and serialization."""
    obs = MonitoringObservation(
        station_id="DL001",
        station_name="Anand Vihar, Delhi",
        timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        lat=28.6508,
        lon=77.3152,
        city="Delhi",
        state="Delhi",
        pm25=145.2,
        pm10=260.5,
        no2=45.0,
        so2=12.3,
        co=1.8,
        o3=34.0,
    )
    assert obs.station_id == "DL001"
    assert obs.pm25 == 145.2
    assert obs.pm10 == 260.5
    assert obs.timestamp.tzinfo == timezone.utc


def test_nullable_pollutants_preserved():
    """Decision D-007: Missing pollutants must remain None/null and never converted to 0.0."""
    obs = MonitoringObservation(
        station_id="HR002",
        station_name="Sector 6, Panchkula",
        timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        lat=30.6942,
        lon=76.8606,
        city="Panchkula",
        state="Haryana",
        pm25=78.5,
        # Other pollutants omitted
    )
    assert obs.pm25 == 78.5
    assert obs.pm10 is None
    assert obs.no2 is None
    assert obs.so2 is None
    assert obs.co is None
    assert obs.o3 is None


def test_invalid_coordinates():
    """Latitude and longitude bounds must be enforced."""
    with pytest.raises(ValidationError):
        MonitoringObservation(
            station_id="DL001",
            station_name="Invalid Lat",
            timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            lat=95.0,  # Invalid: > 90.0
            lon=77.0,
            city="Delhi",
            state="Delhi",
            pm25=50.0,
        )

    with pytest.raises(ValidationError):
        MonitoringObservation(
            station_id="DL001",
            station_name="Invalid Lon",
            timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            lat=28.0,
            lon=185.0,  # Invalid: > 180.0
            city="Delhi",
            state="Delhi",
            pm25=50.0,
        )


def test_negative_pollutant_rejected():
    """Negative concentrations are physically impossible and must fail validation."""
    with pytest.raises(ValidationError):
        MonitoringObservation(
            station_id="DL001",
            station_name="Anand Vihar",
            timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            lat=28.65,
            lon=77.31,
            city="Delhi",
            state="Delhi",
            pm25=-10.0,  # Invalid negative
        )


def test_future_timestamp_rejected():
    """Timestamps far into the future must be rejected."""
    future_time = datetime.now(timezone.utc) + timedelta(days=2)
    with pytest.raises(ValidationError):
        MonitoringObservation(
            station_id="DL001",
            station_name="Anand Vihar",
            timestamp=future_time,
            lat=28.65,
            lon=77.31,
            city="Delhi",
            state="Delhi",
            pm25=50.0,
        )


def test_blank_identifiers_rejected():
    """Empty or whitespace-only station_id / station_name must fail."""
    with pytest.raises(ValidationError):
        MonitoringObservation(
            station_id="   ",
            station_name="Anand Vihar",
            timestamp=datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
            lat=28.65,
            lon=77.31,
            city="Delhi",
            state="Delhi",
        )
