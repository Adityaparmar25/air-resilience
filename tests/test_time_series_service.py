"""Tests for PM2.5 Time-Series Service."""

from datetime import datetime, timedelta, timezone
from schemas.canonical import MonitoringObservation
from services.forecasting.time_series_service import (
    LocalHistoricalBaselineComputer,
    TimeSeriesService,
)


def _create_obs(station_id: str, ts: datetime, pm25: float) -> MonitoringObservation:
    return MonitoringObservation(
        station_id=station_id,
        station_name="Test Station",
        timestamp=ts,
        lat=28.65,
        lon=77.31,
        city="Delhi",
        state="Delhi",
        pm25=pm25,
    )


def test_station_filtering():
    """Service filters strictly by station_id."""
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    obs1 = _create_obs("DL001", base_time, 50.0)
    obs2 = _create_obs("HR001", base_time, 70.0)
    obs3 = _create_obs("dl001", base_time + timedelta(hours=1), 55.0)

    filtered = TimeSeriesService.filter_station([obs1, obs2, obs3], "DL001")
    assert len(filtered) == 2
    assert all(o.station_id.upper() == "DL001" for o in filtered)


def test_chronological_sorting():
    """Service orders timestamps ascending or descending."""
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    obs1 = _create_obs("DL001", base_time + timedelta(hours=2), 60.0)
    obs2 = _create_obs("DL001", base_time, 40.0)
    obs3 = _create_obs("DL001", base_time + timedelta(hours=1), 50.0)

    sorted_asc = TimeSeriesService.sort_chronological([obs1, obs2, obs3], ascending=True)
    assert sorted_asc[0].pm25 == 40.0
    assert sorted_asc[1].pm25 == 50.0
    assert sorted_asc[2].pm25 == 60.0


def test_missing_timestamp_detection():
    """Service detects gaps in hourly observations."""
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    obs1 = _create_obs("DL001", base_time, 50.0)
    obs2 = _create_obs("DL001", base_time + timedelta(hours=1), 52.0)
    # Gap of 4 hours between 11:00 and 15:00
    obs3 = _create_obs("DL001", base_time + timedelta(hours=5), 58.0)

    gaps = TimeSeriesService.detect_missing_timestamps([obs1, obs2, obs3], expected_interval_minutes=60)
    assert len(gaps) == 1
    assert gaps[0]["station_id"] == "DL001"
    assert gaps[0]["gap_duration_hours"] == 4.0
    assert gaps[0]["missing_observations_count"] == 3


def test_local_historical_baseline():
    """Computes mean, median, standard deviation from historical series."""
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    values = [40.0, 50.0, 60.0, 50.0, 55.0]
    observations = [
        _create_obs("DL001", base_time + timedelta(hours=i), val)
        for i, val in enumerate(values)
    ]

    baseline = TimeSeriesService.compute_local_baseline(observations)
    assert baseline["sample_count"] == 5
    assert baseline["mean"] == 51.0
    assert baseline["median"] == 50.0
    assert baseline["std"] > 0
