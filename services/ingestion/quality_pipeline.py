"""Data Quality Pipeline for air quality observations.

Executes sequential quality checks:
raw
  ↓
schema validation & type conversion
  ↓
timestamp normalization
  ↓
duplicate handling
  ↓
range checks
  ↓
quality flags & spike detection (spikes flagged, NOT silently erased)
  ↓
processed data
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from schemas.canonical import MonitoringObservation
from schemas.quality import ObservationQualityRecord, QualityFlag
from services.ingestion.cpcb_adapter import CPCBAdapter


class DataQualityPipeline:
    """End-to-end data quality pipeline ensuring observational integrity."""

    def __init__(
        self,
        spike_delta_threshold: float = 150.0,
        spike_absolute_ceiling: float = 800.0,
        max_time_gap_for_spike_hours: float = 2.5,
        adapter: Optional[CPCBAdapter] = None,
    ):
        self.spike_delta_threshold = spike_delta_threshold
        self.spike_absolute_ceiling = spike_absolute_ceiling
        self.max_time_gap_for_spike_hours = max_time_gap_for_spike_hours
        self.adapter = adapter or CPCBAdapter()

    def process_batch(
        self,
        raw_records: List[Dict[str, Any]],
        is_fixture: bool = True,
    ) -> List[ObservationQualityRecord]:
        """Process a batch of raw records through the data quality pipeline."""
        normalized_records: List[Tuple[Optional[MonitoringObservation], Dict[str, Any], Optional[str]]] = []

        # Step 1 & 2: Schema validation, type conversion, timestamp normalization
        for raw in raw_records:
            try:
                obs, meta = self.adapter.normalize(raw, is_fixture=is_fixture)
                normalized_records.append((obs, meta, None))
            except Exception as e:
                # Capture validation errors rather than silently crashing the pipeline
                meta = {
                    "data_source": "fixture" if is_fixture else "cpcb_live",
                    "raw_payload": raw,
                    "validation_error": str(e),
                }
                normalized_records.append((None, meta, str(e)))

        # Separate successfully normalized records
        valid_items: List[Tuple[MonitoringObservation, Dict[str, Any]]] = [
            (obs, meta) for obs, meta, err in normalized_records if obs is not None
        ]

        # Step 3: Duplicate handling & chronological ordering
        # Sort by station_id and timestamp
        valid_items.sort(key=lambda item: (item[0].station_id, item[0].timestamp))

        results: List[ObservationQualityRecord] = []
        seen_station_timestamps: set[Tuple[str, datetime]] = set()

        # Track previous observation per station for spike detection
        station_prev_obs: Dict[str, MonitoringObservation] = {}

        for obs, meta in valid_items:
            flags: List[QualityFlag] = []
            notes: List[str] = []
            is_usable = True

            key = (obs.station_id, obs.timestamp)
            if key in seen_station_timestamps:
                flags.append(QualityFlag.DUPLICATE_TIMESTAMP)
                notes.append(f"Duplicate timestamp {obs.timestamp.isoformat()} for station {obs.station_id}")
                is_usable = False
            else:
                seen_station_timestamps.add(key)

            # Step 4: Range checks
            if obs.pm25 is not None:
                if obs.pm25 < 0:
                    flags.append(QualityFlag.RANGE_OUTLIER)
                    notes.append(f"Negative PM2.5: {obs.pm25}")
                    is_usable = False
                elif obs.pm25 > 1500.0:
                    flags.append(QualityFlag.RANGE_OUTLIER)
                    notes.append(f"Implausibly high PM2.5 value exceeding physical sensor limit: {obs.pm25}")
            else:
                flags.append(QualityFlag.MISSING_POLLUTANT)
                notes.append("PM2.5 value missing/null")

            # Step 5: Suspicious spike detection (FLAGGED, NOT DELETED)
            if obs.station_id in station_prev_obs and is_usable:
                prev_obs = station_prev_obs[obs.station_id]
                time_diff_hours = (obs.timestamp - prev_obs.timestamp).total_seconds() / 3600.0

                if 0 < time_diff_hours <= self.max_time_gap_for_spike_hours:
                    if obs.pm25 is not None and prev_obs.pm25 is not None:
                        delta = abs(obs.pm25 - prev_obs.pm25)
                        if delta >= self.spike_delta_threshold:
                            flags.append(QualityFlag.SUSPICIOUS_SPIKE)
                            notes.append(
                                f"Suspicious PM2.5 spike detected: delta of {delta:.1f} ug/m3 "
                                f"within {time_diff_hours:.1f} hour(s) (from {prev_obs.pm25} to {obs.pm25})"
                            )

            if obs.pm25 is not None and obs.pm25 >= self.spike_absolute_ceiling:
                if QualityFlag.SUSPICIOUS_SPIKE not in flags:
                    flags.append(QualityFlag.SUSPICIOUS_SPIKE)
                notes.append(
                    f"PM2.5 concentration ({obs.pm25} ug/m3) exceeds absolute alert ceiling ({self.spike_absolute_ceiling} ug/m3)"
                )

            # If no negative flags were raised
            if not flags:
                flags.append(QualityFlag.VALID)

            quality_record = ObservationQualityRecord(
                observation=obs,
                flags=flags,
                is_usable=is_usable,
                raw_metadata=meta,
                quality_notes="; ".join(notes) if notes else None,
            )
            results.append(quality_record)

            if is_usable:
                station_prev_obs[obs.station_id] = obs

        return results
