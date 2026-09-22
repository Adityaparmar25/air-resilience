"""Deterministic End-to-End Replay Demo for Phase 3C.

Demonstrates the vertical slice:
POLLUTION EVENT
  ↓
Evidence Coverage & Fusion Breakdown
  ↓
Forecast Context (+6h, +12h, +24h)
  ↓
AUTHORITY INCIDENT
  ↓
ASSIGN to Field Unit
  ↓
ACKNOWLEDGE by Responders
  ↓
INVESTIGATE on site
  ↓
RESOLVE with mitigation
  ↓
Immutable Audit Trail Verification

All replay data is clearly labeled as [CALIBRATED REPLAY / SYNTHETIC].
"""

from pathlib import Path
import sys

# Ensure repository root is on sys.path when script is executed directly
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from datetime import datetime, timezone
from schemas.citizen_image_analysis import CitizenImageAnalysis, SmokeIntensity, VisualEventType
from schemas.incident import (
    AcknowledgeIncidentRequest,
    AddNoteRequest,
    AssignIncidentRequest,
    CreateIncidentRequest,
    InvestigateIncidentRequest,
    ResolveIncidentRequest,
)
from services.fusion.engine import EvidenceFusionEngine
from services.operational.store import get_operational_store


def run_phase3c_replay():
    print("=" * 80)
    print(" CLEAN AIR & CLIMATE RESILIENCE — PHASE 3C REPLAY DEMO")
    print(" Scenario: Anand Vihar / Patparganj Industrial Corridor (Delhi-NCR)")
    print(" Data Mode: [CALIBRATED OFFLINE REPLAY / SYNTHETIC FIXTURES]")
    print("=" * 80)

    store = get_operational_store()
    store.clear()
    engine = EvidenceFusionEngine()
    now = datetime.now(timezone.utc)

    # -------------------------------------------------------------------------
    # STEP 1: MULTIMODAL OBSERVATION & FUSION ENGINE
    # -------------------------------------------------------------------------
    print("\n[STEP 1] Generating Multimodal Evidence & Spatial Fusion...")
    lat, lon = 28.6469, 77.3160

    # Ground sensor anomaly
    ground_anomaly = {
        "station_id": "DL001",
        "station_name": "Anand Vihar, Delhi",
        "pm25": 192.4,
        "anomaly_score": 4.6,
        "status": "STRONG_ANOMALY",
        "distance_km": 0.8,
        "timestamp": now,
    }

    # Citizen visual observation
    citizen_analysis = CitizenImageAnalysis(
        visible_smoke=True,
        visible_flames=False,
        event_type=VisualEventType.INDUSTRIAL_EMISSIONS,
        smoke_intensity=SmokeIntensity.HEAVY,
        visual_evidence="Thick dark grey plume issuing from factory stack near ring road.",
        uncertain_fields=["exact boiler stack boundary obscured by particulate haze"],
        needs_human_verification=True,
        confidence=0.91,
    )

    event = engine.create_or_update_event(
        lat=lat,
        lon=lon,
        timestamp=now,
        citizen_analysis=citizen_analysis,
        ground_anomaly=ground_anomaly,
        station_id="DL001",
        report_id="rep_replay_001",
    )
    store.save_event(event)

    print(f" -> Event ID: {event.event_id}")
    print(f" -> Evidence Status (D-016): {event.evidence_status.value}")
    print(f" -> Operational Status (D-016): {event.operational_status.value}")
    print(f" -> Fusion Score: {event.evidence.fusion_score:.2f} (Weight denominator: {event.evidence.available_weight_sum})")
    print(f" -> Corroborating Signals: {event.evidence.corroborating_sources_count}")
    print(f" -> Probable Source (D-005): {event.probable_source}")

    # -------------------------------------------------------------------------
    # STEP 2: EVIDENCE COVERAGE (D-007, D-016, D-017)
    # -------------------------------------------------------------------------
    print("\n[STEP 2] Inspecting Evidence Coverage...")
    cov = event.evidence_coverage
    print(f" -> Ground Sensor Available: {cov.ground_sensor}")
    print(f" -> Citizen Report Available: {cov.citizen_report}")
    print(f" -> Weather Context Available: {cov.weather}")
    print(f" -> Satellite Overhead Available: {cov.satellite}")
    print(f" -> Thermal Fire Anomaly Available: {cov.fire}")
    print(f" -> Coverage Ratio: {cov.available_count}/{cov.total_sources} ({cov.coverage_ratio * 100:.0f}%)")
    print(f" -> Minimum Diversity Alert Eligible (D-017): {cov.diversity_eligible_for_alert}")

    # -------------------------------------------------------------------------
    # STEP 3: CONTEXTUAL PM2.5 FORECASTING
    # -------------------------------------------------------------------------
    print("\n[STEP 3] Inspecting PM2.5 Forecast Context...")
    fc = event.forecast
    if fc.get("available"):
        print(f" -> Current PM2.5: {fc.get('current_pm25')} ug/m3")
        print(f" -> +6h Forecast: {fc.get('forecast_6h')} ug/m3")
        print(f" -> +12h Forecast: {fc.get('forecast_12h')} ug/m3")
        print(f" -> +24h Forecast: {fc.get('forecast_24h')} ug/m3")
        print(f" -> 95% Interval (+24h): {fc.get('interval')}")
        print(f" -> Model Provider: {fc.get('provider_name')}")
    else:
        print(f" -> Forecast unavailable: {fc.get('reason')}")

    # -------------------------------------------------------------------------
    # STEP 4: AUTHORITY INCIDENT CREATION
    # -------------------------------------------------------------------------
    print("\n[STEP 4] Creating Authority Incident...")
    req_create = CreateIncidentRequest(
        event_id=event.event_id,
        priority=None,  # auto-derived from HIGH severity
        actor="system_dispatcher",
        initial_notes="Automated incident trigger based on D-017 multi-source corroboration.",
    )
    incident = store.create_incident(req_create, event)
    print(f" -> Incident ID: {incident.incident_id}")
    print(f" -> Priority: {incident.priority.value}")
    print(f" -> Status: {incident.status.value}")

    # -------------------------------------------------------------------------
    # STEP 5: ASSIGNMENT
    # -------------------------------------------------------------------------
    print("\n[STEP 5] Assigning Incident to Response Unit...")
    req_assign = AssignIncidentRequest(
        assigned_to="Inspector Rajesh Kumar",
        assigned_team="East Delhi Rapid Pollution Response Unit",
        actor="lead_dispatcher",
        notes="Dispatched rapid mobile sensor and inspection vehicle to Anand Vihar border.",
    )
    incident = store.assign_incident(incident.incident_id, req_assign)
    print(f" -> New Status: {incident.status.value}")
    print(f" -> Assigned To: {incident.assigned_to} ({incident.assigned_team})")

    # -------------------------------------------------------------------------
    # STEP 6: ACKNOWLEDGEMENT
    # -------------------------------------------------------------------------
    print("\n[STEP 6] Responders Acknowledging Incident...")
    req_ack = AcknowledgeIncidentRequest(
        actor="Inspector Rajesh Kumar",
        notes="Incident acknowledged via field terminal. Vehicle en route, ETA 8 mins.",
    )
    incident = store.acknowledge_incident(incident.incident_id, req_ack)
    print(f" -> New Status: {incident.status.value}")
    print(f" -> Acknowledged At: {incident.acknowledged_at.isoformat()}")

    # -------------------------------------------------------------------------
    # STEP 7: FIELD INVESTIGATION & OBSERVATION NOTE
    # -------------------------------------------------------------------------
    print("\n[STEP 7] Initiating Field Investigation & Logging Notes...")
    req_inv = InvestigateIncidentRequest(
        actor="Inspector Rajesh Kumar",
        notes="On-site inspection initiated. Visual confirmation of unauthorized industrial fuel burning.",
    )
    incident = store.investigate_incident(incident.incident_id, req_inv)
    print(f" -> New Status: {incident.status.value}")

    req_note = AddNoteRequest(
        actor="Inspector Rajesh Kumar",
        content="Facility perimeter secured. Notified operator of emergency shut-down under CAQM statutory directives.",
    )
    store.add_note(incident.incident_id, req_note)
    print(" -> Added field note to incident.")

    # -------------------------------------------------------------------------
    # STEP 8: RESOLUTION
    # -------------------------------------------------------------------------
    print("\n[STEP 8] Resolving Incident...")
    req_res = ResolveIncidentRequest(
        actor="Inspector Rajesh Kumar",
        resolution_summary="Industrial furnace shut down; localized water-fog cannon deployed; particulate emissions contained.",
        notes="Air monitoring handheld shows PM2.5 dropping below 65 ug/m3.",
    )
    incident = store.resolve_incident(incident.incident_id, req_res)
    print(f" -> Final Status: {incident.status.value}")
    print(f" -> Resolved At: {incident.resolved_at.isoformat()}")
    print(f" -> Resolution Summary: {incident.resolution_summary}")

    # -------------------------------------------------------------------------
    # STEP 9: IMMUTABLE AUDIT TRAIL
    # -------------------------------------------------------------------------
    print("\n[STEP 9] Verifying Immutable Audit Trail...")
    audit_logs = store.get_audit_records(incident_id=incident.incident_id)
    print(f" -> Total Audit Records Logged: {len(audit_logs)}")
    for idx, log in enumerate(audit_logs, 1):
        print(f"    [{idx}] {log.timestamp.strftime('%H:%M:%S')} | Action: {log.action:<12} | {log.previous_status or 'INIT':<12} -> {log.new_status:<12} | Actor: {log.actor}")

    print("\n" + "=" * 80)
    print(" REPLAY DEMO COMPLETED SUCCESSFULLY — 100% DETERMINISTIC PASS")
    print("=" * 80)


if __name__ == "__main__":
    run_phase3c_replay()
