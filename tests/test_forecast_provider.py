"""Tests for Forecast Provider Abstraction."""

from datetime import datetime, timedelta, timezone
import pytest
from pydantic import ValidationError
from schemas.canonical import MonitoringObservation
from services.forecasting.base import (
    ForecastRequest,
    PredictionPoint,
)
from services.forecasting.baseline import BaselineTimeSeriesForecastProvider
from services.forecasting.bigquery_timesfm import BigQueryTimesFMForecastProvider


def _make_series(station_id: str, count: int = 24) -> list[MonitoringObservation]:
    base = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
    return [
        MonitoringObservation(
            station_id=station_id,
            station_name="Test Station",
            timestamp=base + timedelta(hours=i),
            lat=28.65,
            lon=77.31,
            city="Delhi",
            state="Delhi",
            pm25=50.0 + (i % 10) * 3.0,
        )
        for i in range(count)
    ]


def test_baseline_forecast_horizon_length():
    """Provider produces exactly the requested number of horizon points."""
    provider = BaselineTimeSeriesForecastProvider()
    history = _make_series("DL001", count=24)
    req = ForecastRequest(station_id="DL001", history=history, horizon=12)

    resp = provider.forecast(req)

    assert resp.station_id == "DL001"
    assert resp.horizon == 12
    assert len(resp.predictions) == 12
    assert resp.provider_type == "development_baseline"


def test_forecast_bounds_integrity():
    """Every prediction point must satisfy lower_bound <= pm25_forecast <= upper_bound."""
    provider = BaselineTimeSeriesForecastProvider()
    history = _make_series("DL001", count=48)
    req = ForecastRequest(station_id="DL001", history=history, horizon=24)

    resp = provider.forecast(req)

    for pt in resp.predictions:
        assert pt.lower_bound <= pt.pm25_forecast
        assert pt.pm25_forecast <= pt.upper_bound
        assert pt.lower_bound >= 0.0


def test_forecast_to_contract_dict():
    """Verify output dictionary matches the exact Phase 3A contract keys."""
    provider = BaselineTimeSeriesForecastProvider()
    history = _make_series("DL001", count=24)
    req = ForecastRequest(station_id="DL001", history=history, horizon=6)

    resp = provider.forecast(req)
    contract_dict = resp.to_contract_dict()

    assert "station_id" in contract_dict
    assert "horizon" in contract_dict
    assert "predictions" in contract_dict
    assert contract_dict["horizon"] == 6

    first_pred = contract_dict["predictions"][0]
    expected_keys = {"timestamp", "pm25_forecast", "lower_bound", "upper_bound"}
    assert set(first_pred.keys()) == expected_keys


def test_forecast_unknown_station_raises_error():
    """Requesting forecast for a station not present in history must raise ValueError."""
    provider = BaselineTimeSeriesForecastProvider()
    history = _make_series("DL001", count=10)
    req = ForecastRequest(station_id="UNKNOWN_999", history=history, horizon=24)

    with pytest.raises(ValueError, match="No historical observations found matching station_id"):
        provider.forecast(req)


def test_bigquery_provider_fallback_behavior():
    """BigQuery provider safely falls back to baseline when GCP credentials unconfigured."""
    provider = BigQueryTimesFMForecastProvider(fallback_to_baseline=True)
    history = _make_series("DL001", count=12)
    req = ForecastRequest(station_id="DL001", history=history, horizon=6)

    resp = provider.forecast(req)
    assert resp.station_id == "DL001"
    assert len(resp.predictions) == 6
    assert "fallback" in resp.provider_type
