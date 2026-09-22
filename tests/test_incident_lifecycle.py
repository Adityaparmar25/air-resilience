"""Tests for Authority Incident Workflow, Operational Lifecycle, and Audit Logging.

Verifies:
- Operational state transitions (DETECTED -> ALERTED -> ASSIGNED -> ACKNOWLEDGED -> INVESTIGATING -> RESOLVED / DISMISSED)
- Server-side validation rejecting invalid transitions (Decision D-016)
- Minimum evidence diversity rules for automated alerting (Decision D-017)
- Immutable audit trail creation for every authority transition and note
- REST API compliance for authority incident endpoints
"""

from datetime import datetime, timezone
from fastapi.testclient import TestClient
import pytest

from apps.api.main import create_app
from schemas.event import (
    EventSeverity,
    EventStatus,
    EvidenceBreakdown,
    EvidenceCoverage,
    EvidenceSignal,
    EvidenceStatus,
    LocationCell,
    OperationalStatus,
    PollutionEvent,
)
from schemas.incident import (
    AcknowledgeIncidentRequest,
    AddNoteRequest,
    AssignIncidentRequest,
    CreateIncidentRequest,
    DismissIncidentRequest,
    IncidentPriority,
    IncidentStatus,
    InvestigateIncidentRequest,
    ResolveIncidentRequest,
)
from services.operational.store import get_operational_store


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def clean_store():
    store = get_operational_store()
    store.clear()
    return store


def make_dummy_event(
    event_id: str = "ev_test_lifecycle",
    diversity_eligible: bool = True,
    fusion_score: float = 0.78,
) -> PollutionEvent:
    now = datetime.now(timezone.utc)
    return PollutionEvent(
        event_id=event_id,
        timestamp=now,
        location=LocationCell(lat=28.65, lng=77.31, cell_id="grid_28.65_77.31"),
        evidence_status=EvidenceStatus.HIGH_CONFIDENCE,
        operational_status=OperationalStatus.ALERTED if diversity_eligible else OperationalStatus.DETECTED,
        severity=EventSeverity.HIGH,
        evidence=EvidenceBreakdown(
            signals={
                "ground_sensor": EvidenceSignal(
                    source="ground_sensor",
                    timestamp=now,
                    location={"lat": 28.65, "lng": 77.31},
                    signal_type="pm25_anomaly",
                    score=0.85,
                    weight=0.30,
                    availability=True,
                ),
                "citizen_report": EvidenceSignal(
                    source="citizen_report",
                    timestamp=now,
                    location={"lat": 28.65, "lng": 77.31},
                    signal_type="visible_smoke",
                    score=0.80,
                    weight=0.15,
                    availability=diversity_eligible,
                ),
            },
            fusion_score=fusion_score,
            available_weight_sum=0.45,
            available_sources_count=2 if diversity_eligible else 1,
            corroborating_sources_count=2 if diversity_eligible else 1,
            explanation_text="Corroborated ground sensor and citizen report.",
        ),
        evidence_coverage=EvidenceCoverage(
            ground_sensor=True,
            citizen_report=diversity_eligible,
            available_count=2 if diversity_eligible else 1,
            total_sources=5,
            coverage_ratio=0.4 if diversity_eligible else 0.2,
            diversity_eligible_for_alert=diversity_eligible,
        ),
        probable_source="Likely industrial plume",
    )


def test_create_incident_diversity_eligible(clean_store, client):
    """Event with >= 2 evidence classes automatically escalates to ALERTED status (D-017)."""
    event = make_dummy_event("ev_diverse_123", diversity_eligible=True, fusion_score=0.80)
    clean_store.save_event(event)

    payload = {
        "event_id": event.event_id,
        "priority": "HIGH",
        "actor": "system_dispatcher",
        "initial_notes": "High confidence corroborated smoke and ground PM2.5 spike.",
    }
    res = client.post("/api/v1/incidents", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "ALERTED"
    assert data["priority"] == "HIGH"
    assert data["event_id"] == event.event_id


def test_create_incident_single_source_requires_manual_review(clean_store, client):
    """Event with single evidence class defaults to DETECTED (requiring human review per D-017)."""
    event = make_dummy_event("ev_single_456", diversity_eligible=False, fusion_score=0.50)
    clean_store.save_event(event)

    payload = {
        "event_id": event.event_id,
        "actor": "system_dispatcher",
    }
    res = client.post("/api/v1/incidents", json=payload)
    assert res.status_code == 201
    data = res.json()
    assert data["status"] == "DETECTED"


def test_full_incident_lifecycle(clean_store, client):
    """Verifies complete valid lifecycle: ALERTED -> ASSIGNED -> ACKNOWLEDGED -> INVESTIGATING -> RESOLVED."""
    event = make_dummy_event("ev_lifecycle_789", diversity_eligible=True)
    clean_store.save_event(event)

    # 1. Create Incident -> ALERTED
    res1 = client.post("/api/v1/incidents", json={"event_id": event.event_id, "actor": "dispatcher_1"})
    assert res1.status_code == 201
    inc_id = res1.json()["incident_id"]
    assert res1.json()["status"] == "ALERTED"

    # 2. Assign Incident -> ASSIGNED
    res2 = client.post(
        f"/api/v1/incidents/{inc_id}/assign",
        json={
            "assigned_to": "Officer Sharma",
            "assigned_team": "East Delhi Enforcement Unit",
            "actor": "dispatcher_1",
            "notes": "Dispatched patrol vehicle to Anand Vihar industrial border.",
        },
    )
    assert res2.status_code == 200
    assert res2.json()["status"] == "ASSIGNED"
    assert res2.json()["assigned_to"] == "Officer Sharma"

    # 3. Acknowledge Incident -> ACKNOWLEDGED
    res3 = client.post(
        f"/api/v1/incidents/{inc_id}/acknowledge",
        json={"actor": "Officer Sharma", "notes": "Patrol en route; ETA 12 minutes."},
    )
    assert res3.status_code == 200
    assert res3.json()["status"] == "ACKNOWLEDGED"
    assert res3.json()["acknowledged_at"] is not None

    # 4. Investigate Incident -> INVESTIGATING
    res4 = client.post(
        f"/api/v1/incidents/{inc_id}/investigate",
        json={"actor": "Officer Sharma", "notes": "On site. Verified illegal waste burning at edge of scrap facility."},
    )
    assert res4.status_code == 200
    assert res4.json()["status"] == "INVESTIGATING"
    assert res4.json()["investigating_at"] is not None

    # 5. Resolve Incident -> RESOLVED
    res5 = client.post(
        f"/api/v1/incidents/{inc_id}/resolve",
        json={
            "actor": "Officer Sharma",
            "resolution_summary": "Extinguished localized waste fire; water mist sprayed; source doused.",
            "notes": "PM2.5 sensor levels returning towards local diurnal baseline.",
        },
    )
    assert res5.status_code == 200
    assert res5.json()["status"] == "RESOLVED"
    assert res5.json()["resolved_at"] is not None
    assert "Extinguished" in res5.json()["resolution_summary"]


def test_invalid_status_transition_rejected(clean_store, client):
    """Server-side state machine must strictly reject illegal state jumps."""
    event = make_dummy_event("ev_invalid_transition", diversity_eligible=False)
    clean_store.save_event(event)

    # Starts in DETECTED
    res = client.post("/api/v1/incidents", json={"event_id": event.event_id})
    inc_id = res.json()["incident_id"]

    # Illegal transition: DETECTED directly to RESOLVED without assignment/investigation
    bad_res = client.post(
        f"/api/v1/incidents/{inc_id}/resolve",
        json={"actor": "tester", "resolution_summary": "Skipped investigation steps."},
    )
    assert bad_res.status_code == 400
    assert "Invalid status transition" in bad_res.json()["detail"]


def test_dismiss_incident_workflow(clean_store, client):
    """Verifies dismissing an incident from ALERTED to DISMISSED."""
    event = make_dummy_event("ev_dismiss_me", diversity_eligible=True)
    clean_store.save_event(event)

    res = client.post("/api/v1/incidents", json={"event_id": event.event_id})
    inc_id = res.json()["incident_id"]

    dismiss_res = client.post(
        f"/api/v1/incidents/{inc_id}/dismiss",
        json={
            "actor": "senior_reviewer",
            "dismissal_reason": "Inspection confirmed legitimate boiler steam exhaust, not unpermitted particulate combustion.",
        },
    )
    assert dismiss_res.status_code == 200
    assert dismiss_res.json()["status"] == "DISMISSED"
    assert dismiss_res.json()["dismissed_at"] is not None


def test_add_field_note(clean_store, client):
    """Operational notes are timestamped and preserved."""
    event = make_dummy_event("ev_notes_test")
    clean_store.save_event(event)

    res = client.post("/api/v1/incidents", json={"event_id": event.event_id})
    inc_id = res.json()["incident_id"]

    note_res = client.post(
        f"/api/v1/incidents/{inc_id}/notes",
        json={"actor": "drone_pilot", "content": "Aerial thermal drone footage uploaded to central dispatch."},
    )
    assert note_res.status_code == 200
    note_data = note_res.json()
    assert note_data["actor"] == "drone_pilot"
    assert "thermal drone" in note_data["content"]

    # Verify note in incident detail
    detail = client.get(f"/api/v1/incidents/{inc_id}").json()
    assert len(detail["notes"]) >= 1


def test_immutable_audit_log(clean_store, client):
    """Every authority transition creates an immutable audit record."""
    event = make_dummy_event("ev_audit_test")
    clean_store.save_event(event)

    # 1. Create
    res = client.post("/api/v1/incidents", json={"event_id": event.event_id, "actor": "auto_monitor"})
    inc_id = res.json()["incident_id"]

    # 2. Assign
    client.post(
        f"/api/v1/incidents/{inc_id}/assign",
        json={"assigned_to": "Field Unit Alpha", "actor": "lead_dispatcher"},
    )

    # 3. Add note
    client.post(
        f"/api/v1/incidents/{inc_id}/notes",
        json={"actor": "unit_alpha_lead", "content": "Arrived at coordinate."},
    )

    # Fetch audit log
    audit_res = client.get(f"/api/v1/incidents/{inc_id}/audit")
    assert audit_res.status_code == 200
    logs = audit_res.json()

    assert len(logs) >= 3
    actions = [l["action"] for l in logs]
    assert "CREATE" in actions
    assert "ASSIGN" in actions
    assert "ADD_NOTE" in actions
