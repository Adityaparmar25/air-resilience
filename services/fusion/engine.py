"""Evidence Fusion Engine.

Implements the multi-source weighted evidence fusion formula agreed in decision.md D-006:
    event_score = sum(weight_i * evidence_i) / sum(available weights)
with strict adherence to D-007 (missing evidence is null/unavailable, NOT zero).
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from schemas.citizen_image_analysis import CitizenImageAnalysis, VisualEventType
from schemas.event import (
    EventSeverity,
    EventStatus,
    EvidenceBreakdown,
    EvidenceSignal,
    LocationCell,
    PollutionEvent,
)
from services.fusion.correlation import generate_cell_id
from services.fusion.explanation import generate_event_explanation


class EvidenceFusionEngine:
    """Core evidence fusion engine for pollution event creation and state progression."""

    # Starting prototype weights from Decision D-006
    DEFAULT_WEIGHTS = {
        "ground_sensor": 0.30,
        "satellite": 0.20,
        "citizen_report": 0.15,
        "weather": 0.15,
        "fire": 0.20,
    }

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()

    def calculate_fusion_score(
        self, signals: Dict[str, EvidenceSignal]
    ) -> tuple[float, float, int, int]:
        """Compute normalized fusion score over available sources only.

        Returns (fusion_score, available_weight_sum, available_count, corroborating_count).
        Strictly excludes unavailable sources from denominator per Decision D-007.
        """
        available_weight_sum = 0.0
        weighted_score_sum = 0.0
        available_count = 0
        corroborating_count = 0

        for source_name, signal in signals.items():
            if signal.availability and signal.score is not None:
                weight = self.weights.get(source_name, 0.10)
                available_weight_sum += weight
                weighted_score_sum += weight * signal.score
                available_count += 1
                # Consider signal corroborating if score >= 0.40
                if signal.score >= 0.40:
                    corroborating_count += 1

        if available_weight_sum <= 0.0:
            return 0.0, 0.0, 0, 0

        fusion_score = round(weighted_score_sum / available_weight_sum, 3)
        return fusion_score, round(available_weight_sum, 2), available_count, corroborating_count

    def determine_event_state(
        self,
        fusion_score: float,
        corroboration_count: int,
        citizen_analysis: Optional[CitizenImageAnalysis] = None,
        ground_anomaly_score: Optional[float] = None,
    ) -> tuple[EventStatus, EventSeverity]:
        """Determine lifecycle state and severity based on score and corroboration."""
        # 1. Check False Positive condition
        if citizen_analysis is not None:
            if not citizen_analysis.visible_smoke and not citizen_analysis.visible_flames:
                if ground_anomaly_score is None or ground_anomaly_score < 2.0:
                    return EventStatus.FALSE_POSITIVE, EventSeverity.LOW

        # 2. State classification
        if fusion_score >= 0.75 and corroboration_count >= 2:
            status = EventStatus.HIGH_CONFIDENCE
            severity = EventSeverity.HIGH if fusion_score < 0.88 else EventSeverity.CRITICAL
        elif fusion_score >= 0.50 or (corroboration_count >= 2 and fusion_score >= 0.40):
            status = EventStatus.CORROBORATED
            severity = EventSeverity.MODERATE if fusion_score < 0.70 else EventSeverity.HIGH
        elif fusion_score >= 0.30 or corroboration_count >= 1:
            status = EventStatus.POSSIBLE
            severity = EventSeverity.LOW if fusion_score < 0.45 else EventSeverity.MODERATE
        else:
            status = EventStatus.FALSE_POSITIVE
            severity = EventSeverity.LOW

        return status, severity

    def create_or_update_event(
        self,
        lat: float,
        lon: float,
        timestamp: datetime,
        citizen_analysis: Optional[CitizenImageAnalysis] = None,
        ground_anomaly: Optional[Dict[str, Any]] = None,
        existing_event: Optional[PollutionEvent] = None,
        report_id: Optional[str] = None,
        station_id: Optional[str] = None,
    ) -> PollutionEvent:
        """Fuse signals and construct/update canonical PollutionEvent."""
        signals: Dict[str, EvidenceSignal] = {}

        # 1. Ground Sensor Signal
        if ground_anomaly and ground_anomaly.get("pm25") is not None:
            pm25 = float(ground_anomaly["pm25"])
            z_score = float(ground_anomaly.get("anomaly_score", 0.0))

            # Normalize ground anomaly score between 0.0 and 1.0 (z=0 -> 0.1, z>=4.0 -> 1.0)
            ground_norm_score = min(1.0, max(0.0, z_score / 4.0)) if z_score > 0 else 0.1

            signals["ground_sensor"] = EvidenceSignal(
                source="ground_sensor",
                timestamp=ground_anomaly.get("timestamp") or timestamp,
                location={"lat": lat, "lng": lon},
                signal_type="pm25_anomaly",
                score=round(ground_norm_score, 2),
                weight=self.weights["ground_sensor"],
                availability=True,
                metadata={
                    "station_id": station_id or ground_anomaly.get("station_id"),
                    "station_name": ground_anomaly.get("station_name"),
                    "pm25": pm25,
                    "z_score": z_score,
                    "distance_km": ground_anomaly.get("distance_km"),
                },
            )
        else:
            signals["ground_sensor"] = EvidenceSignal(
                source="ground_sensor",
                timestamp=timestamp,
                location={"lat": lat, "lng": lon},
                signal_type="pm25_anomaly",
                score=None,
                weight=self.weights["ground_sensor"],
                availability=False,
                metadata={"reason": "No nearby ground monitoring sensor available or measurement null"},
            )

        # 2. Citizen Report Signal
        if citizen_analysis:
            # Score based on confidence and intensity
            if not citizen_analysis.visible_smoke and not citizen_analysis.visible_flames:
                cit_score = 0.0
            else:
                intensity_multipliers = {
                    "none": 0.0,
                    "low": 0.5,
                    "moderate": 0.75,
                    "heavy": 0.90,
                    "dense": 1.0,
                }
                mult = intensity_multipliers.get(citizen_analysis.smoke_intensity.value, 0.7)
                cit_score = round(citizen_analysis.confidence * mult, 2)

            signals["citizen_report"] = EvidenceSignal(
                source="citizen_report",
                timestamp=timestamp,
                location={"lat": lat, "lng": lon},
                signal_type="visible_smoke",
                score=cit_score,
                weight=self.weights["citizen_report"],
                availability=True,
                metadata={
                    "report_id": report_id,
                    "visible_smoke": citizen_analysis.visible_smoke,
                    "visible_flames": citizen_analysis.visible_flames,
                    "smoke_intensity": citizen_analysis.smoke_intensity.value,
                    "confidence": citizen_analysis.confidence,
                    "visual_evidence": citizen_analysis.visual_evidence,
                },
            )
        else:
            signals["citizen_report"] = EvidenceSignal(
                source="citizen_report",
                timestamp=timestamp,
                location={"lat": lat, "lng": lon},
                signal_type="visible_smoke",
                score=None,
                weight=self.weights["citizen_report"],
                availability=False,
                metadata={"reason": "No citizen photograph provided"},
            )

        # 3. Satellite (Sentinel-5P / Earth Engine) - Scheduled for expansion in Phase 3C
        signals["satellite"] = EvidenceSignal(
            source="satellite",
            timestamp=timestamp,
            location={"lat": lat, "lng": lon},
            signal_type="tropospheric_no2_aod",
            score=None,
            weight=self.weights["satellite"],
            availability=False,
            metadata={"status": "unavailable", "note": "Sentinel-5P orbital overpass unavailable at current timestamp"},
        )

        # 4. Weather (IMD) - Scheduled for expansion in Phase 3C
        signals["weather"] = EvidenceSignal(
            source="weather",
            timestamp=timestamp,
            location={"lat": lat, "lng": lon},
            signal_type="wind_dispersion_alignment",
            score=None,
            weight=self.weights["weather"],
            availability=False,
            metadata={"status": "unavailable", "note": "Local meteorological station offline"},
        )

        # 5. Fire (NASA FIRMS) - Scheduled for expansion in Phase 3C
        signals["fire"] = EvidenceSignal(
            source="fire",
            timestamp=timestamp,
            location={"lat": lat, "lng": lon},
            signal_type="thermal_anomaly",
            score=None,
            weight=self.weights["fire"],
            availability=False,
            metadata={"status": "unavailable", "note": "MODIS/VIIRS thermal anomaly detection unavailable"},
        )

        # Compute fusion score strictly across available signals
        fusion_score, avail_weight, avail_count, corrob_count = self.calculate_fusion_score(signals)

        # Determine status and severity
        status, severity = self.determine_event_state(
            fusion_score=fusion_score,
            corroboration_count=corrob_count,
            citizen_analysis=citizen_analysis,
            ground_anomaly_score=ground_anomaly.get("anomaly_score") if ground_anomaly else None,
        )

        # Determine probable source (Decision D-005)
        probable_source = None
        if citizen_analysis and citizen_analysis.visible_smoke:
            source_map = {
                VisualEventType.INDUSTRIAL_EMISSIONS: "Likely industrial/combustion plume",
                VisualEventType.BIOMASS_BURNING: "Likely agricultural/biomass burning",
                VisualEventType.OPEN_WASTE_BURNING: "Likely open-waste combustion",
                VisualEventType.DUST: "Likely fugitive dust event",
                VisualEventType.VEHICLE_EXHAUST: "Likely localized vehicular emissions",
                VisualEventType.UNKNOWN: "Unclassified combustion plume",
            }
            probable_source = source_map.get(citizen_analysis.event_type, "Likely combustion event")
        elif ground_anomaly and ground_anomaly.get("anomaly_score", 0.0) >= 2.0:
            probable_source = "Unverified ground particulate elevation"

        # Generate "Why was this event created?" narrative
        explanation = generate_event_explanation(
            signals=signals,
            fusion_score=fusion_score,
            status=status,
            severity=severity,
            probable_source=probable_source,
            corroboration_count=corrob_count,
        )

        breakdown = EvidenceBreakdown(
            signals=signals,
            fusion_score=fusion_score,
            available_weight_sum=avail_weight,
            available_sources_count=avail_count,
            corroborating_sources_count=corrob_count,
            explanation_text=explanation,
        )

        cell_id = generate_cell_id(lat, lon)
        loc = LocationCell(lat=round(lat, 4), lng=round(lon, 4), cell_id=cell_id)

        resolved_station_id = station_id or (ground_anomaly.get("station_id") if ground_anomaly else None)

        # Merge with existing event if deduplicating
        if existing_event:
            linked_reports = list(set(existing_event.report_ids + ([report_id] if report_id else [])))
            linked_stations = list(set(existing_event.station_ids + ([resolved_station_id] if resolved_station_id else [])))

            existing_event.evidence = breakdown
            existing_event.status = status
            existing_event.severity = severity
            existing_event.report_ids = linked_reports
            existing_event.station_ids = linked_stations
            if probable_source:
                existing_event.probable_source = probable_source
            return existing_event

        event = PollutionEvent(
            location=loc,
            status=status,
            event_type="combustion_event" if "combustion" in str(probable_source).lower() else "localized_particulate_elevation",
            severity=severity,
            evidence=breakdown,
            probable_source=probable_source,
            human_verification_required=True,
            report_ids=[report_id] if report_id else [],
            station_ids=[resolved_station_id] if resolved_station_id else [],
        )
        return event
