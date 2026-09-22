"""Tests for Spatio-Temporal Correlation and Event Deduplication."""

from datetime import datetime, timedelta, timezone
from schemas.event import (
    EventSeverity,
    EventStatus,
    EvidenceBreakdown,
    LocationCell,
    PollutionEvent,
)
from services.fusion.correlation import (
    SpatioTemporalCorrelationService,
    haversine_distance_km,
)


def _make_dummy_event(lat: float, lon: float, ts: datetime) -> PollutionEvent:
    return PollutionEvent(
        event_id="ev_existing_1",
        timestamp=ts,
        location=LocationCell(lat=lat, lng=lon, cell_id=f"cell_{lat:.2f}_{lon:.2f}"),
        status=EventStatus.POSSIBLE,
        severity=EventSeverity.MODERATE,
        evidence=EvidenceBreakdown(
            signals={},
            fusion_score=0.5,
            available_weight_sum=0.45,
            available_sources_count=2,
            corroborating_sources_count=1,
            explanation_text="Test",
        ),
    )


def test_haversine_distance():
    """Verify distance calculation between Anand Vihar and Sector 62 Noida."""
    # Anand Vihar (28.6508, 77.3152) to Sector 62 Noida (28.6245, 77.3639)
    dist = haversine_distance_km(28.6508, 77.3152, 28.6245, 77.3639)
    # Expected distance is ~5.5 km
    assert 4.5 <= dist <= 6.5


def test_nearby_station_discovery():
    """Finds stations near Anand Vihar within 10 km."""
    stations = SpatioTemporalCorrelationService.find_nearby_stations(28.6508, 77.3152, max_distance_km=10.0)
    assert len(stations) >= 1
    # First station should be Anand Vihar (DL001) at ~0 km
    assert stations[0][0] == "DL001"
    assert stations[0][2] < 1.0


def test_matching_event_deduplication():
    """Identifies existing event within spatial radius and time window to prevent duplicate creation."""
    now = datetime.now(timezone.utc)
    existing_event = _make_dummy_event(28.65, 77.31, now)

    # 1. Nearby report: 1.2 km away, 30 minutes later -> MATCH
    match = SpatioTemporalCorrelationService.find_matching_event(
        lat=28.66,
        lon=77.32,
        timestamp=now + timedelta(minutes=30),
        active_events=[existing_event],
        spatial_radius_km=5.0,
        temporal_window_hours=3.0,
    )
    assert match is not None
    matched_ev, dist, time_diff = match
    assert matched_ev.event_id == "ev_existing_1"
    assert dist < 5.0
    assert time_diff < 3.0

    # 2. Far away report: 45 km away -> NO MATCH
    no_match = SpatioTemporalCorrelationService.find_matching_event(
        lat=28.36,
        lon=76.92,
        timestamp=now,
        active_events=[existing_event],
        spatial_radius_km=5.0,
    )
    assert no_match is None

    # 3. Old report: 8 hours later -> NO MATCH
    stale_match = SpatioTemporalCorrelationService.find_matching_event(
        lat=28.65,
        lon=77.31,
        timestamp=now + timedelta(hours=8),
        active_events=[existing_event],
        temporal_window_hours=3.0,
    )
    assert stale_match is None
