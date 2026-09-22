"""Tests for Evidence Fusion Engine and State Transitions."""

from datetime import datetime, timezone
import pytest
from schemas.citizen_image_analysis import (
    CitizenImageAnalysis,
    SmokeIntensity,
    VisualEventType,
)
from schemas.event import EventSeverity, EventStatus, EvidenceSignal
from services.fusion.engine import EvidenceFusionEngine
from services.ingestion.imd_adapter import IMDAdapter


def test_evidence_fusion_weighted_score():
    """Decision D-006 & D-007: Weights normalized strictly across available signals only."""
    engine = EvidenceFusionEngine()
    now = datetime.now(timezone.utc)

    # Available: Ground (0.30 weight, 0.8 score), Citizen (0.15 weight, 0.9 score)
    # Unavailable: Satellite (0.20), Weather (0.15), Fire (0.20)
    signals = {
        "ground_sensor": EvidenceSignal(
            source="ground_sensor",
            timestamp=now,
            location={"lat": 28.65, "lng": 77.31},
            signal_type="pm25_anomaly",
            score=0.8,
            weight=0.30,
            availability=True,
        ),
        "citizen_report": EvidenceSignal(
            source="citizen_report",
            timestamp=now,
            location={"lat": 28.65, "lng": 77.31},
            signal_type="visible_smoke",
            score=0.9,
            weight=0.15,
            availability=True,
        ),
        "satellite": EvidenceSignal(
            source="satellite",
            timestamp=now,
            location={"lat": 28.65, "lng": 77.31},
            signal_type="tropospheric_no2_aod",
            score=None,  # Unavailable
            weight=0.20,
            availability=False,
        ),
    }

    fusion_score, avail_weight, avail_count, corrob_count = engine.calculate_fusion_score(signals)

    # Expected available weight: 0.30 + 0.15 = 0.45
    assert avail_weight == 0.45
    assert avail_count == 2
    assert corrob_count == 2

    # Expected weighted score: (0.30 * 0.8 + 0.15 * 0.9) / 0.45 = (0.24 + 0.135) / 0.45 = 0.375 / 0.45 = 0.833
    expected_score = round(0.375 / 0.45, 3)
    assert fusion_score == expected_score


def test_missing_evidence_not_zero():
    """Decision D-007: Missing evidence must not be converted to 0.0 or penalized."""
    engine = EvidenceFusionEngine()
    now = datetime.now(timezone.utc)

    # Only citizen report is available
    signals = {
        "citizen_report": EvidenceSignal(
            source="citizen_report",
            timestamp=now,
            location={"lat": 28.65, "lng": 77.31},
            signal_type="visible_smoke",
            score=0.85,
            weight=0.15,
            availability=True,
        ),
        "ground_sensor": EvidenceSignal(
            source="ground_sensor",
            timestamp=now,
            location={"lat": 28.65, "lng": 77.31},
            signal_type="pm25_anomaly",
            score=None,
            weight=0.30,
            availability=False,
        ),
    }

    fusion_score, avail_weight, avail_count, _ = engine.calculate_fusion_score(signals)
    assert avail_weight == 0.15
    # Score should be exactly the citizen report score, not diluted to 0.15 * 0.85 / 1.0
    assert fusion_score == 0.85


def test_state_transitions():
    """Verify state transitions: POSSIBLE, CORROBORATED, HIGH_CONFIDENCE."""
    engine = EvidenceFusionEngine()

    # 1. Single uncorroborated report -> POSSIBLE
    st1, sev1 = engine.determine_event_state(fusion_score=0.45, corroboration_count=1)
    assert st1 == EventStatus.POSSIBLE

    # 2. Corroborated signals -> CORROBORATED
    st2, sev2 = engine.determine_event_state(fusion_score=0.65, corroboration_count=2)
    assert st2 == EventStatus.CORROBORATED
    assert sev2 in {EventSeverity.MODERATE, EventSeverity.HIGH}

    # 3. High confidence multi-source corroboration -> HIGH_CONFIDENCE
    st3, sev3 = engine.determine_event_state(fusion_score=0.82, corroboration_count=3)
    assert st3 == EventStatus.HIGH_CONFIDENCE
    assert sev3 in {EventSeverity.HIGH, EventSeverity.CRITICAL}


def test_false_positive_determination():
    """When citizen image confirms absence of smoke and ground is clean -> FALSE_POSITIVE."""
    engine = EvidenceFusionEngine()
    clean_analysis = CitizenImageAnalysis(
        visible_smoke=False,
        visible_flames=False,
        event_type=VisualEventType.UNKNOWN,
        smoke_intensity=SmokeIntensity.NONE,
        visual_evidence="Clear blue sky; no smoke visible.",
        uncertain_fields=[],
        needs_human_verification=False,
        confidence=0.95,
    )

    status, severity = engine.determine_event_state(
        fusion_score=0.10,
        corroboration_count=0,
        citizen_analysis=clean_analysis,
        ground_anomaly_score=0.0,
    )
    assert status == EventStatus.FALSE_POSITIVE


def test_create_event_generates_explanation():
    """Event creation must generate structured explanation text."""
    engine = EvidenceFusionEngine(
        weather_adapter=IMDAdapter(simulate_timeout=True)
    )
    now = datetime.now(timezone.utc)

    analysis = CitizenImageAnalysis(
        visible_smoke=True,
        visible_flames=False,
        event_type=VisualEventType.INDUSTRIAL_EMISSIONS,
        smoke_intensity=SmokeIntensity.HEAVY,
        visual_evidence="Dense black smoke plume from factory chimney.",
        uncertain_fields=[],
        needs_human_verification=True,
        confidence=0.89,
    )
    ground_anomaly = {
        "station_id": "DL001",
        "station_name": "Anand Vihar, Delhi",
        "pm25": 185.0,
        "anomaly_score": 4.5,
        "status": "STRONG_ANOMALY",
        "distance_km": 1.5,
        "timestamp": now,
    }

    event = engine.create_or_update_event(
        lat=28.65,
        lon=77.31,
        timestamp=now,
        citizen_analysis=analysis,
        ground_anomaly=ground_anomaly,
        report_id="rep_test_123",
    )

    assert event.status in {EventStatus.CORROBORATED, EventStatus.HIGH_CONFIDENCE}
    assert event.probable_source == "Likely industrial/combustion plume"
    assert "rep_test_123" in event.report_ids
    assert "DL001" in event.station_ids
    assert len(event.evidence.explanation_text) > 20
    assert "Anand Vihar" in event.evidence.explanation_text
    assert "unavailable" in event.evidence.explanation_text.lower()
