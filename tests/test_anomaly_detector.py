"""Tests for Explainable Anomaly Detector."""

from datetime import datetime, timedelta, timezone
import pytest
from schemas.canonical import MonitoringObservation
from services.anomaly.detector import (
    AnomalyDetectionConfig,
    AnomalyResult,
    AnomalyStatus,
    ExplainableAnomalyDetector,
)


def _make_obs(ts: datetime, pm25: float) -> MonitoringObservation:
    return MonitoringObservation(
        station_id="DL001",
        station_name="Anand Vihar, Delhi",
        timestamp=ts,
        lat=28.6508,
        lon=77.3152,
        city="Delhi",
        state="Delhi",
        pm25=pm25,
    )


def test_anomaly_classification_normal():
    """Observations within normal baseline variance must be classified as NORMAL."""
    detector = ExplainableAnomalyDetector()
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    # Baseline history with mean 50, std ~ 5
    history = [
        _make_obs(base_time - timedelta(hours=i), 50.0 + (i % 3))
        for i in range(1, 10)
    ]
    target = _make_obs(base_time, 53.0)

    result = detector.detect(target, history)

    assert result.status == AnomalyStatus.NORMAL
    assert result.station_id == "DL001"
    assert result.pm25 == 53.0
    assert result.expected_pm25 == pytest.approx(51.0, abs=2.0)
    assert result.anomaly_score < 2.0


def test_anomaly_classification_elevated():
    """Readings crossing the elevated threshold must be classified as ELEVATED."""
    detector = ExplainableAnomalyDetector()
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    # Baseline history with mean ~ 45, std ~ 5
    history = [
        _make_obs(base_time - timedelta(hours=i), 45.0)
        for i in range(1, 10)
    ]
    # Observed reading 60 -> z = (60 - 45)/5 = 3.0 >= 2.0 (elevated threshold)
    target = _make_obs(base_time, 60.0)

    result = detector.detect(target, history)

    assert result.status == AnomalyStatus.ELEVATED
    assert result.anomaly_score >= 2.0
    assert result.anomaly_score < 3.5


def test_anomaly_classification_strong_anomaly():
    """Readings with high z-score or exceeding strong ceiling must be STRONG_ANOMALY."""
    detector = ExplainableAnomalyDetector()
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    history = [
        _make_obs(base_time - timedelta(hours=i), 40.0)
        for i in range(1, 10)
    ]
    # Jump to 250 -> z = (250 - 40)/5 = 42.0 >> 3.5
    target = _make_obs(base_time, 250.0)

    result = detector.detect(target, history)

    assert result.status == AnomalyStatus.STRONG_ANOMALY
    assert result.anomaly_score >= 3.5


def test_contract_dict_exact_keys():
    """Verify output dictionary contains contract keys and separated anomaly output fields."""
    detector = ExplainableAnomalyDetector()
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    target = _make_obs(base_time, 180.0)
    result = detector.detect(target, [])

    d = result.to_contract_dict()
    expected_keys = {
        "station_id",
        "timestamp",
        "pm25",
        "expected_pm25",
        "anomaly_score",
        "status",
        "z_score",
        "absolute_threshold_triggered",
        "classification_reason",
        "classification",
    }
    assert set(d.keys()) == expected_keys
    assert d["status"] in {"NORMAL", "ELEVATED", "STRONG_ANOMALY"}
    assert isinstance(d["anomaly_score"], (int, float))
    assert isinstance(d["z_score"], float)
    assert isinstance(d["absolute_threshold_triggered"], bool)
    assert isinstance(d["classification_reason"], str)
    assert d["classification"] == d["status"]


def test_missing_pm25_raises_error():
    """Evaluating an observation with null PM2.5 must raise an informative ValueError."""
    detector = ExplainableAnomalyDetector()
    base_time = datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc)
    obs = MonitoringObservation(
        station_id="DL001",
        station_name="Anand Vihar",
        timestamp=base_time,
        lat=28.65,
        lon=77.31,
        city="Delhi",
        state="Delhi",
        pm25=None,
    )
    with pytest.raises(ValueError, match="PM2.5 measurement is null"):
        detector.detect(obs, [])
