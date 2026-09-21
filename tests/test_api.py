"""Tests for FastAPI HTTP Endpoints."""

import json
from datetime import datetime, timezone
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)
FIXTURE_DIR = Path(__file__).resolve().parent.parent / "data" / "fixtures"


def test_health_endpoint():
    """GET /health must return 200 with status ok."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "air-resilience-api"
    assert "version" in data
    assert "timestamp" in data


def test_get_station_series_success():
    """GET /api/v1/stations/DL001/series returns 200 with observations and baseline."""
    response = client.get("/api/v1/stations/DL001/series?limit=24")
    assert response.status_code == 200
    data = response.json()
    assert data["station_id"] == "DL001"
    assert data["observation_count"] > 0
    assert len(data["observations"]) > 0
    assert "baseline" in data
    assert "mean" in data["baseline"]
    assert data["data_source"] == "fixture"


def test_get_station_series_not_found():
    """GET /api/v1/stations/NONEXISTENT/series returns 404."""
    response = client.get("/api/v1/stations/NONEXISTENT_999/series")
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


def test_post_anomaly_detection_success():
    """POST /api/v1/anomaly evaluates target observation against history."""
    payload = {
        "observation": {
            "station_id": "DL001",
            "station_name": "Anand Vihar, Delhi",
            "timestamp": "2026-01-20T12:00:00Z",
            "lat": 28.6508,
            "lon": 77.3152,
            "city": "Delhi",
            "state": "Delhi",
            "pm25": 195.0,
        },
        "history": [
            {
                "station_id": "DL001",
                "station_name": "Anand Vihar, Delhi",
                "timestamp": f"2026-01-20T0{i}:00:00Z",
                "lat": 28.6508,
                "lon": 77.3152,
                "city": "Delhi",
                "state": "Delhi",
                "pm25": 60.0 + i,
            }
            for i in range(5)
        ],
    }

    response = client.post("/api/v1/anomaly", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["station_id"] == "DL001"
    assert data["pm25"] == 195.0
    assert data["status"] in {"ELEVATED", "STRONG_ANOMALY"}
    assert data["anomaly_score"] > 2.0
    assert "explanation" in data


def test_post_anomaly_null_pm25_rejected():
    """POST /api/v1/anomaly with null PM2.5 returns 422."""
    payload = {
        "observation": {
            "station_id": "DL001",
            "station_name": "Anand Vihar, Delhi",
            "timestamp": "2026-01-20T12:00:00Z",
            "lat": 28.6508,
            "lon": 77.3152,
            "city": "Delhi",
            "state": "Delhi",
            "pm25": None,
        },
        "history": [],
    }
    response = client.post("/api/v1/anomaly", json=payload)
    assert response.status_code == 422


def test_post_forecast_success():
    """POST /api/v1/forecast produces exact requested horizon."""
    with open(FIXTURE_DIR / "forecast_input.json", "r", encoding="utf-8") as f:
        fixture_payload = json.load(f)

    # Clean payload
    payload = {
        "station_id": fixture_payload["station_id"],
        "horizon": 24,
        "history": fixture_payload["history"],
    }

    response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["station_id"] == "DL001"
    assert data["horizon"] == 24
    assert len(data["predictions"]) == 24

    for pred in data["predictions"]:
        assert pred["lower_bound"] <= pred["pm25_forecast"]
        assert pred["pm25_forecast"] <= pred["upper_bound"]


def test_post_forecast_mismatched_station():
    """POST /api/v1/forecast with station not in history returns 400."""
    with open(FIXTURE_DIR / "forecast_input.json", "r", encoding="utf-8") as f:
        fixture_payload = json.load(f)

    payload = {
        "station_id": "WRONG_STATION_ID",
        "horizon": 12,
        "history": fixture_payload["history"],
    }
    response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code == 400


def test_post_forecast_invalid_horizon():
    """POST /api/v1/forecast with horizon outside [1, 72] returns 422."""
    payload = {
        "station_id": "DL001",
        "horizon": 0,  # Invalid: ge=1
        "history": [],
    }
    response = client.post("/api/v1/forecast", json=payload)
    assert response.status_code == 422
