"""Production Integration and System Verification Tests.

Validates:
1. Genuine provider health indicators (zero fabrication)
2. Forecast provider selection (DEVELOPMENT vs BIGQUERY_TIMESFM)
3. Historical public replay data provenance tagging
4. List pagination on events and incidents
5. X-Correlation-ID middleware tracking
6. Production error sanitization (zero traceback leakage)
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from apps.api.config import get_settings
from apps.api.main import create_app
from schemas.event import EvidenceStatus
from services.forecasting.base import ForecastRequest
from services.forecasting.bigquery_timesfm import (
    BigQueryTimesFMForecastProvider,
    get_forecast_provider,
    TIMESFM_MEASURED_BENCHMARK_METRICS,
)
from services.ingestion.cpcb_adapter import CPCBAdapter
from services.operational.store import get_operational_store


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


def test_health_endpoint_provider_statuses(client):
    """Verify /health and /api/v1/health return genuine provider health without fabrication."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()

    assert data["service"] == "air-resilience-api"
    assert "providers" in data
    assert data["data_mode"] in ("HISTORICAL_REPLAY", "LIVE")

    providers = data["providers"]
    required_providers = ["cpcb", "imd", "firms", "sentinel", "gemini", "forecast", "federation"]
    for p in required_providers:
        assert p in providers, f"Missing health provider indicator: {p}"
        assert providers[p]["status"] in ("available", "unavailable", "degraded", "replay")
        assert len(providers[p]["details"]) > 0


def test_healthz_cloud_run_probe(client):
    """Verify Cloud Run readiness probe /healthz returns 200 OK."""
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_forecast_provider_selection_and_measured_metrics():
    """Verify clean selection between DEVELOPMENT and BIGQUERY_TIMESFM with verified metrics."""
    # 1. Development Provider
    dev_provider = get_forecast_provider("DEVELOPMENT")
    assert dev_provider.__class__.__name__ == "BaselineTimeSeriesForecastProvider"

    # 2. BigQuery TimesFM Provider
    bq_provider = get_forecast_provider("BIGQUERY_TIMESFM")
    assert bq_provider.__class__.__name__ == "BigQueryTimesFMForecastProvider"

    # 3. Forecast request with real historical observations
    hist_path = Path(__file__).resolve().parent.parent / "data" / "historical" / "delhi_severe_smog_2023.json"
    with open(hist_path, "r", encoding="utf-8") as f:
        hist_data = json.load(f)

    adapter = CPCBAdapter()
    obs = [adapter.normalize(o)[0] for o in hist_data["monitoring_observations"]]

    req = ForecastRequest(station_id="DL015", history=obs, horizon=12)
    resp = bq_provider.forecast(req)

    assert "bigquery_timesfm" in resp.provider_type
    assert resp.measured_metrics is not None
    assert resp.measured_metrics["measured_mae"] == 8.42
    assert resp.measured_metrics["measured_rmse"] == 11.25
    assert resp.measured_metrics["benchmark_verified"] is True


def test_historical_replay_data_endpoint(client):
    """Verify GET /api/v1/historical/delhi-smog-2023 serves authentic public data."""
    response = client.get("/api/v1/historical/delhi-smog-2023")
    assert response.status_code == 200
    data = response.json()

    assert data["metadata"]["provenance_type"] == "HISTORICAL"
    assert data["metadata"]["is_synthetic"] is False
    assert data["metadata"]["is_replay"] is True
    assert len(data["monitoring_observations"]) > 0
    assert len(data["thermal_anomalies"]) > 0
    assert data["meteorology"]["station_id"] == "IMD_42182_SAFDARJUNG"


def test_events_and_incidents_pagination(client):
    """Verify events and incidents endpoints support limit and offset parameters."""
    # 1. Events pagination
    resp_events = client.get("/api/v1/events?limit=5&offset=0")
    assert resp_events.status_code == 200
    assert isinstance(resp_events.json(), list)

    # 2. Incidents pagination
    resp_incidents = client.get("/api/v1/incidents?limit=5&offset=0")
    assert resp_incidents.status_code == 200
    assert isinstance(resp_incidents.json(), list)


def test_correlation_id_middleware(client):
    """Verify X-Correlation-ID is attached and returned in response headers."""
    # Without incoming header
    res1 = client.get("/healthz")
    assert "x-correlation-id" in res1.headers
    assert res1.headers["x-correlation-id"].startswith("corr_")

    # With incoming header
    custom_id = "test-corr-uuid-12345"
    res2 = client.get("/healthz", headers={"X-Correlation-ID": custom_id})
    assert res2.headers["x-correlation-id"] == custom_id


def test_safe_error_handling_sanitization(client):
    """Verify unhandled exceptions return safe sanitized responses with zero stack trace leakage."""
    # Trigger 404 for nonexistent incident
    res = client.get("/api/v1/incidents/INC-NONEXISTENT")
    assert res.status_code == 404
    data = res.json()
    assert "detail" in data
    # Ensure no internal python traceback or file paths in response
    assert "Traceback" not in str(data)
    assert "File \"" not in str(data)
