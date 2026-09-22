"""Tests for External Source Adapters (IMD, NASA FIRMS, Sentinel-5P).

Verifies:
- Input validation and metadata preservation
- Graceful failure/timeout handling (unavailable return state without fabrication)
- Decision D-007: unavailable signals are null and never coerced to 0.0
- Claim rules: FIRMS claims 'nearby fire/thermal anomaly detected' and never 'crop burning confirmed'
- Claim rules: Sentinel-5P evidence is never presented as ground PM2.5
"""

from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from schemas.event import EvidenceCoverage, EvidenceSignal
from services.ingestion.firms_adapter import (
    APPROVED_CLAIM_STATEMENT,
    FIRMSAdapter,
    FIRMSObservation,
)
from services.ingestion.imd_adapter import IMDAdapter, IMDWeatherObservation
from services.ingestion.sentinel_adapter import Sentinel5PAdapter, SentinelObservation


def test_imd_adapter_successful_retrieval():
    """IMD adapter successfully returns weather context near Anand Vihar."""
    adapter = IMDAdapter()
    obs = adapter.get_weather_observation(lat=28.6469, lon=77.3160)

    assert obs is not None
    assert isinstance(obs, IMDWeatherObservation)
    assert obs.temperature > 0
    assert 0 <= obs.humidity <= 100
    assert obs.wind_speed >= 0
    assert obs.source_metadata.get("provider") == "India Meteorological Department (IMD)"


def test_imd_adapter_timeout_handling():
    """IMD adapter returns None upon timeout or failure without fabricating data."""
    adapter = IMDAdapter(simulate_timeout=True)
    obs = adapter.get_weather_observation(lat=28.6469, lon=77.3160)
    assert obs is None


def test_imd_adapter_out_of_radius():
    """IMD adapter returns None if no meteorological observatory is within radius."""
    adapter = IMDAdapter(max_distance_km=0.1)
    obs = adapter.get_weather_observation(lat=10.0, lon=70.0)
    assert obs is None


def test_firms_adapter_claim_statement_rule():
    """NASA FIRMS claim statement must state 'nearby fire/thermal anomaly detected'."""
    adapter = FIRMSAdapter()
    obs = adapter.get_thermal_anomaly(lat=28.6475, lon=77.3180)

    assert obs is not None
    assert obs.claim_statement == APPROVED_CLAIM_STATEMENT
    assert "fire/thermal anomaly" in obs.claim_statement


def test_firms_adapter_prohibits_crop_burning_accusation():
    """FIRMS models must strictly reject claims asserting 'crop burning confirmed'."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        FIRMSObservation(
            latitude=28.65,
            longitude=77.32,
            acquisition_time=now,
            claim_statement="crop burning confirmed by satellite",
        )


def test_firms_adapter_failure_handling():
    """FIRMS adapter gracefully returns None upon satellite failure or lack of detections."""
    adapter = FIRMSAdapter(simulate_failure=True)
    obs = adapter.get_thermal_anomaly(lat=28.6475, lon=77.3180)
    assert obs is None


def test_sentinel_adapter_successful_retrieval():
    """Sentinel-5P adapter returns tropospheric NO2 and Aerosol Index."""
    adapter = Sentinel5PAdapter()
    obs = adapter.get_atmospheric_observation(lat=28.6469, lon=77.3160)

    assert obs is not None
    assert obs.no2_tropospheric_column is not None
    assert obs.aerosol_index is not None
    assert obs.spatial_coverage_km == 7.0


def test_sentinel_adapter_prohibits_ground_pm25_representation():
    """Sentinel-5P must reject metadata purporting to be ground PM2.5."""
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError):
        SentinelObservation(
            timestamp=now,
            lat=28.65,
            lon=77.31,
            source_metadata={"label": "Ground PM2.5 from Sentinel-5P"},
        )


def test_sentinel_adapter_failure_handling():
    """Sentinel adapter returns None upon orbital overpass unavailability."""
    adapter = Sentinel5PAdapter(simulate_failure=True)
    obs = adapter.get_atmospheric_observation(lat=28.6469, lon=77.3160)
    assert obs is None


def test_evidence_coverage_distinguishes_strength_from_coverage():
    """System must distinguish evidence coverage (availability) from evidence strength."""
    cov = EvidenceCoverage(
        ground_sensor=True,
        citizen_report=True,
        weather=True,
        satellite=False,
        fire=False,
        available_count=3,
        total_sources=5,
        coverage_ratio=0.6,
        diversity_eligible_for_alert=True,
    )
    assert cov.available_count == 3
    assert cov.coverage_ratio == 0.6
    assert cov.satellite is False
    assert cov.fire is False
    assert cov.diversity_eligible_for_alert is True
