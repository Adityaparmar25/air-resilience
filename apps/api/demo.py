"""Milestone 1 Demonstration Script.

Runs the complete vertical engineering slice:
fixture/CPCB data
  ↓
canonical normalization
  ↓
quality checks
  ↓
station time series
  ↓
explainable anomaly detection
  ↓
forecast abstraction
  ↓
FastAPI verification
"""

import json
from pathlib import Path
import sys

# Ensure repository root is on sys.path when script is executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi.testclient import TestClient

from apps.api.main import app
from services.anomaly.detector import ExplainableAnomalyDetector
from services.forecasting.base import ForecastRequest
from services.forecasting.baseline import BaselineTimeSeriesForecastProvider
from services.forecasting.time_series_service import TimeSeriesService
from services.ingestion.cpcb_adapter import CPCBAdapter
from services.ingestion.quality_pipeline import DataQualityPipeline

FIXTURE_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "fixtures" / "normal_series.json"


def run_demo() -> None:
    print("=" * 70)
    print("  AIR RESILIENCE NETWORK - MILESTONE 1 VERIFICATION DEMO")
    print("=" * 70)

    # 1. Ingestion & Adapter
    print("\n[Stage 1] Ingesting CPCB data from fixture...")
    adapter = CPCBAdapter(default_fixture_path=str(FIXTURE_PATH))
    raw_records = adapter.fetch(is_fixture=True)
    print(f"  -> Fetched {len(raw_records)} raw records for station {raw_records[0].get('StationId')}")

    # 2. Quality Pipeline
    print("\n[Stage 2] Running Data-Quality Pipeline...")
    pipeline = DataQualityPipeline(adapter=adapter)
    quality_records = pipeline.process_batch(raw_records, is_fixture=True)
    valid_count = sum(1 for qr in quality_records if qr.is_usable)
    print(f"  -> Processed {len(quality_records)} records. Usable: {valid_count}/{len(quality_records)}")
    observations = [qr.observation for qr in quality_records]

    # 3. Station Time Series Service
    print("\n[Stage 3] Assembling Station Time Series...")
    series = TimeSeriesService.sort_chronological(observations, ascending=True)
    baseline = TimeSeriesService.compute_local_baseline(series)
    gaps = TimeSeriesService.detect_missing_timestamps(series)
    print(f"  -> Station: {series[0].station_id} ({series[0].station_name})")
    print(f"  -> Range: {series[0].timestamp.isoformat()} to {series[-1].timestamp.isoformat()}")
    print(f"  -> Baseline Mean: {baseline['mean']} ug/m3, Std: {baseline['std']} ug/m3, Median: {baseline['median']} ug/m3")
    print(f"  -> Missing telemetry gaps detected: {len(gaps)}")

    # 4. Explainable Anomaly Detection
    print("\n[Stage 4] Evaluating Explainable Anomaly Detector...")
    detector = ExplainableAnomalyDetector()
    target_obs = series[-1]
    history_obs = series[:-1]
    result = detector.detect(target_obs, history_obs)
    print("  -> Anomaly Output Contract:")
    print(json.dumps(result.to_contract_dict(), indent=4))
    print(f"  -> Explanation: {result.explanation}")

    # 5. Forecast Abstraction
    print("\n[Stage 5] Generating 24-Hour Horizon PM2.5 Forecast...")
    provider = BaselineTimeSeriesForecastProvider()
    forecast_req = ForecastRequest(station_id="DL001", history=series, horizon=24)
    forecast_resp = provider.forecast(forecast_req)
    print(f"  -> Provider: {forecast_resp.provider_type}")
    print(f"  -> Generated {len(forecast_resp.predictions)} hourly predictions.")
    print("  -> First 3 predictions:")
    for pred in forecast_resp.predictions[:3]:
        print(f"     * {pred.timestamp.isoformat()} => {pred.pm25_forecast} ug/m3 (95% CI: [{pred.lower_bound}, {pred.upper_bound}])")

    # 6. FastAPI Verification
    print("\n[Stage 6] Verifying FastAPI HTTP Endpoints via TestClient...")
    client = TestClient(app)

    # Health
    health = client.get("/health").json()
    print(f"  -> GET /health: status={health['status']}, service={health['service']}")

    # Station series
    series_api = client.get("/api/v1/stations/DL001/series?limit=12").json()
    print(f"  -> GET /api/v1/stations/DL001/series: count={series_api['observation_count']}, baseline_mean={series_api['baseline']['mean']}")

    # Anomaly endpoint
    anomaly_payload = {
        "observation": target_obs.model_dump(mode="json"),
        "history": [obs.model_dump(mode="json") for obs in history_obs],
    }
    anomaly_api = client.post("/api/v1/anomaly", json=anomaly_payload).json()
    print(f"  -> POST /api/v1/anomaly: status={anomaly_api['status']}, score={anomaly_api['anomaly_score']}")

    # Forecast endpoint
    forecast_payload = {
        "station_id": "DL001",
        "horizon": 24,
        "history": [obs.model_dump(mode="json") for obs in series],
    }
    forecast_api = client.post("/api/v1/forecast", json=forecast_payload).json()
    print(f"  -> POST /api/v1/forecast: horizon={forecast_api['horizon']}, predictions={len(forecast_api['predictions'])}")

    print("\n" + "=" * 70)
    print("  MILESTONE 1 DEMO COMPLETED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    run_demo()
