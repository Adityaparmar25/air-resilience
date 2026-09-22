"""API Integration Tests for Citizen Reports and Event Engine Endpoints."""

from io import BytesIO
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from apps.api.main import app
from services.operational.store import get_operational_store

client = TestClient(app)
SAMPLE_DIR = Path(__file__).resolve().parent.parent / "data" / "sample_images"


@pytest.fixture(autouse=True)
def clean_store():
    """Ensure operational store is clean before each test."""
    store = get_operational_store()
    store.clear()
    yield
    store.clear()


def test_submit_report_json():
    """Submit report via application/json."""
    payload = {
        "lat": 28.6508,
        "lon": 77.3152,
        "description": "Smoke seen near Anand Vihar bus terminal",
    }
    resp = client.post("/api/v1/reports", json=payload)
    assert resp.status_code == 201
    data = resp.json()
    assert "report_id" in data
    assert data["lat"] == 28.6508
    assert data["status"] == "PENDING_ANALYSIS"
    assert data["has_image"] is False


def test_submit_report_multipart():
    """Submit report with JPEG image upload."""
    with open(SAMPLE_DIR / "industrial_smoke.jpg", "rb") as f:
        img_bytes = f.read()

    files = {"file": ("smoke.jpg", img_bytes, "image/jpeg")}
    data = {
        "lat": "28.6508",
        "lon": "77.3152",
        "description": "Heavy black plume rising from industrial facility",
    }
    resp = client.post("/api/v1/reports", data=data, files=files)
    assert resp.status_code == 201
    res_data = resp.json()
    assert res_data["has_image"] is True
    assert res_data["status"] == "PENDING_ANALYSIS"


def test_submit_report_invalid_file_type_rejected():
    """Uploading non-image file must return 415 Unsupported Media Type."""
    fake_pdf = b"%PDF-1.4 fake pdf"
    files = {"file": ("doc.pdf", fake_pdf, "application/pdf")}
    data = {"lat": "28.65", "lon": "77.31"}
    resp = client.post("/api/v1/reports", data=data, files=files)
    assert resp.status_code == 415


def test_analyze_citizen_report():
    """Execute Gemini analysis on submitted report photograph."""
    # 1. Submit report with image
    with open(SAMPLE_DIR / "industrial_smoke.jpg", "rb") as f:
        img_bytes = f.read()

    files = {"file": ("smoke.jpg", img_bytes, "image/jpeg")}
    data = {"lat": "28.6508", "lon": "77.3152", "description": "Factory smoke"}
    sub_resp = client.post("/api/v1/reports", data=data, files=files)
    report_id = sub_resp.json()["report_id"]

    # 2. Trigger analysis
    analyze_resp = client.post(f"/api/v1/reports/{report_id}/analyze")
    assert analyze_resp.status_code == 200
    res = analyze_resp.json()

    assert res["status"] == "ANALYZED"
    assert res["analysis"] is not None
    assert res["analysis"]["visible_smoke"] is True
    assert res["analysis"]["event_type"] == "industrial_emissions"
    assert res["analysis"]["confidence"] >= 0.80


def test_detect_event_and_fusion():
    """POST /api/v1/events/detect fuses citizen report and nearby ground anomaly."""
    # 1. Submit and analyze report
    with open(SAMPLE_DIR / "industrial_smoke.jpg", "rb") as f:
        img_bytes = f.read()

    files = {"file": ("smoke.jpg", img_bytes, "image/jpeg")}
    data = {"lat": "28.6508", "lon": "77.3152", "description": "Smoke plume"}
    sub_resp = client.post("/api/v1/reports", data=data, files=files)
    report_id = sub_resp.json()["report_id"]
    client.post(f"/api/v1/reports/{report_id}/analyze")

    # 2. Trigger event detection & evidence fusion
    detect_resp = client.post("/api/v1/events/detect", json={"report_id": report_id})
    assert detect_resp.status_code == 200
    event_data = detect_resp.json()

    assert "event_id" in event_data
    assert event_data["status"] in {"CORROBORATED", "HIGH_CONFIDENCE", "POSSIBLE"}
    assert event_data["evidence"]["fusion_score"] > 0.0
    assert "signals" in event_data["evidence"]
    assert "citizen_report" in event_data["evidence"]["signals"]
    assert "ground_sensor" in event_data["evidence"]["signals"]
    assert "Why was this event created" in event_data["evidence"]["explanation_text"] or len(event_data["evidence"]["explanation_text"]) > 20
    assert report_id in event_data["report_ids"]


def test_event_deduplication():
    """Second report in same area links to existing event rather than creating duplicate."""
    # Report 1
    r1 = client.post("/api/v1/reports", json={"lat": 28.6508, "lon": 77.3152, "description": "Smoke 1"}).json()
    ev1 = client.post("/api/v1/events/detect", json={"report_id": r1["report_id"]}).json()

    # Report 2 (nearby: 500m away, 10 min later)
    r2 = client.post("/api/v1/reports", json={"lat": 28.6530, "lon": 77.3170, "description": "Smoke 2"}).json()
    ev2 = client.post("/api/v1/events/detect", json={"report_id": r2["report_id"]}).json()

    # Should be the exact same event_id
    assert ev1["event_id"] == ev2["event_id"]
    assert r1["report_id"] in ev2["report_ids"]
    assert r2["report_id"] in ev2["report_ids"]

    # Listing events should only return 1 event
    events_list = client.get("/api/v1/events").json()
    assert len(events_list) == 1


def test_get_event_by_id():
    """GET /api/v1/events/{id} returns full event details."""
    r = client.post("/api/v1/reports", json={"lat": 28.6508, "lon": 77.3152}).json()
    ev = client.post("/api/v1/events/detect", json={"report_id": r["report_id"]}).json()
    event_id = ev["event_id"]

    get_resp = client.get(f"/api/v1/events/{event_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["event_id"] == event_id

    # 404 for non-existent
    not_found_resp = client.get("/api/v1/events/ev_nonexistent_999")
    assert not_found_resp.status_code == 404
