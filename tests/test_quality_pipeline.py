"""Tests for DataQualityPipeline."""

import pytest
from services.ingestion.quality_pipeline import DataQualityPipeline
from schemas.quality import QualityFlag


def test_quality_pipeline_detects_duplicates():
    """Duplicate observations with identical (station_id, timestamp) must be flagged and marked unusable."""
    pipeline = DataQualityPipeline()
    records = [
        {
            "StationId": "DL001",
            "Date": "2026-01-15 10:00:00",
            "PM2.5": 85.0,
            "Latitude": 28.65,
            "Longitude": 77.31,
            "City": "Delhi",
            "State": "Delhi",
        },
        {
            "StationId": "DL001",
            "Date": "2026-01-15 10:00:00",  # Duplicate timestamp
            "PM2.5": 90.0,
            "Latitude": 28.65,
            "Longitude": 77.31,
            "City": "Delhi",
            "State": "Delhi",
        },
    ]

    results = pipeline.process_batch(records)
    assert len(results) == 2
    assert results[0].is_usable is True
    assert QualityFlag.VALID in results[0].flags
    assert results[1].is_usable is False
    assert QualityFlag.DUPLICATE_TIMESTAMP in results[1].flags


def test_quality_pipeline_flags_suspicious_spike_without_deleting():
    """Suspicious spikes must be tagged with SUSPICIOUS_SPIKE, retained, and not silently dropped."""
    pipeline = DataQualityPipeline(spike_delta_threshold=150.0)
    records = [
        {
            "StationId": "DL001",
            "Date": "2026-01-15 10:00:00",
            "PM2.5": 60.0,
            "Latitude": 28.65,
            "Longitude": 77.31,
            "City": "Delhi",
            "State": "Delhi",
        },
        {
            "StationId": "DL001",
            "Date": "2026-01-15 11:00:00",
            "PM2.5": 280.0,  # +220 jump in 1 hour -> spike!
            "Latitude": 28.65,
            "Longitude": 77.31,
            "City": "Delhi",
            "State": "Delhi",
        },
    ]

    results = pipeline.process_batch(records)
    assert len(results) == 2
    # First observation normal
    assert QualityFlag.VALID in results[0].flags

    # Second observation flagged as spike but NOT deleted
    spike_rec = results[1]
    assert QualityFlag.SUSPICIOUS_SPIKE in spike_rec.flags
    assert spike_rec.observation.pm25 == 280.0
    assert "Suspicious PM2.5 spike detected" in (spike_rec.quality_notes or "")


def test_quality_pipeline_flags_missing_pollutants():
    """Missing PM2.5 must receive MISSING_POLLUTANT flag."""
    pipeline = DataQualityPipeline()
    records = [
        {
            "StationId": "DL001",
            "Date": "2026-01-15 10:00:00",
            "PM2.5": None,
            "Latitude": 28.65,
            "Longitude": 77.31,
            "City": "Delhi",
            "State": "Delhi",
        }
    ]
    results = pipeline.process_batch(records)
    assert len(results) == 1
    assert QualityFlag.MISSING_POLLUTANT in results[0].flags
