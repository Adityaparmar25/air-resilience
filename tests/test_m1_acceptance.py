"""Milestone 1 Acceptance Test: End-to-End Vertical Slice Verification.

Validates the complete contract sequence:
fixture/CPCB data
  ↓
normalization
  ↓
quality checks
  ↓
station time series
  ↓
anomaly detection
  ↓
forecast provider
  ↓
FastAPI response
"""

import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from schemas.canonical import MonitoringObservation
from schemas.quality import QualityFlag
from services.anomaly.detector import AnomalyStatus, ExplainableAnomalyDetector
from services.forecasting.base import ForecastRequest
from services.forecasting.baseline import BaselineTimeSeriesForecastProvider
from services.forecasting.time_series_service import TimeSeriesService
from services.ingestion.cpcb_adapter import CPCBAdapter
from services.ingestion.quality_pipeline import DataQualityPipeline

client = TestClient(app)
FIXTURE_PATH = Path(__file__).resolve().parent.parent / "data" / "fixtures" / "normal_series.json"


def test_m1_end_to_end_vertical_slice():
    """Execute the full Milestone 1 data and API chain."""

    # 1. Ingest raw CPCB fixture data
    adapter = CPCBAdapter(default_fixture_path=str(FIXTURE_PATH))
    raw_records = adapter.fetch(is_fixture=True)
    assert len(raw_records) >= 10, "Expected at least 10 observations in normal series fixture"

    # 2. Canonical Normalization
    first_obs, meta = adapter.normalize(raw_records[0], is_fixture=True)
    assert isinstance(first_obs, MonitoringObservation)
    assert first_obs.station_id == "DL001"
    assert first_obs.pm25 is not None
    assert meta["data_source"] == "fixture"

    # 3. Data-Quality Pipeline
    pipeline = DataQualityPipeline(adapter=adapter)
    quality_records = pipeline.process_batch(raw_records, is_fixture=True)
    assert len(quality_records) == len(raw_records)
    assert all(qr.is_usable for qr in quality_records)
    assert all(QualityFlag.VALID in qr.flags for qr in quality_records)

    # Extract clean normalized observations
    observations = [qr.observation for qr in quality_records]

    # 4. Station Time Series Service
    dl_series = TimeSeriesService.filter_station(observations, "DL001")
    sorted_series = TimeSeriesService.sort_chronological(dl_series, ascending=True)
    assert sorted_series[0].timestamp < sorted_series[-1].timestamp

    gaps = TimeSeriesService.detect_missing_timestamps(sorted_series)
    # The normal series fixture has uninterrupted hourly cadence
    assert len(gaps) == 0

    baseline = TimeSeriesService.compute_local_baseline(sorted_series)
    assert baseline["sample_count"] == len(sorted_series)
    assert baseline["mean"] > 0.0
    assert baseline["std"] > 0.0

    # 5. Explainable Anomaly Detection
    detector = ExplainableAnomalyDetector()
    target_obs = sorted_series[-1]
    history_obs = sorted_series[:-1]

    anomaly_result = detector.detect(target_obs, history_obs)
    contract_dict = anomaly_result.to_contract_dict()

    assert contract_dict["station_id"] == "DL001"
    assert contract_dict["status"] in {"NORMAL", "ELEVATED", "STRONG_ANOMALY"}
    assert contract_dict["anomaly_score"] >= 0.0
    assert "explanation" in anomaly_result.model_dump()

    # 6. Forecast Abstraction
    forecast_provider = BaselineTimeSeriesForecastProvider()
    forecast_req = ForecastRequest(station_id="DL001", history=sorted_series, horizon=24)
    forecast_resp = forecast_provider.forecast(forecast_req)
    forecast_dict = forecast_resp.to_contract_dict()

    assert forecast_dict["station_id"] == "DL001"
    assert forecast_dict["horizon"] == 24
    assert len(forecast_dict["predictions"]) == 24
    for pred in forecast_dict["predictions"]:
        assert pred["lower_bound"] <= pred["pm25_forecast"] <= pred["upper_bound"]

    # 7. FastAPI Endpoint Responses
    # Health check
    health_resp = client.get("/health")
    assert health_resp.status_code == 200
    assert health_resp.json()["status"] == "ok"

    # Station series endpoint
    series_resp = client.get("/api/v1/stations/DL001/series?limit=24")
    assert series_resp.status_code == 200
    series_data = series_resp.json()
    assert series_data["station_id"] == "DL001"
    assert series_data["observation_count"] == len(sorted_series)
    assert "baseline" in series_data

    # Anomaly endpoint
    api_anomaly_resp = client.post(
        "/api/v1/anomaly",
        json={
            "observation": target_obs.model_dump(mode="json"),
            "history": [obs.model_dump(mode="json") for obs in history_obs],
        },
    )
    assert api_anomaly_resp.status_code == 200
    api_anomaly_data = api_anomaly_resp.json()
    assert api_anomaly_data["station_id"] == "DL001"
    assert api_anomaly_data["status"] == contract_dict["status"]

    # Forecast endpoint
    api_forecast_resp = client.post(
        "/api/v1/forecast",
        json={
            "station_id": "DL001",
            "horizon": 24,
            "history": [obs.model_dump(mode="json") for obs in sorted_series],
        },
    )
    assert api_forecast_resp.status_code == 200
    api_forecast_data = api_forecast_resp.json()
    assert api_forecast_data["station_id"] == "DL001"
    assert api_forecast_data["horizon"] == 24
    assert len(api_forecast_data["predictions"]) == 24
