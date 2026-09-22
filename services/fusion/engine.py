"""Evidence Fusion Engine.

Implements the multi-source weighted evidence fusion formula agreed in decision.md D-006:
    event_score = sum(weight_i * evidence_i) / sum(available weights)
with strict adherence to:
- D-007 (missing evidence is null/unavailable, NOT zero)
- D-016 (architectural separation of evidence_status from operational_status)
- D-017 (minimum evidence diversity for operational alerting: >= 2 independent sources)
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from schemas.citizen_image_analysis import CitizenImageAnalysis, VisualEventType
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
from services.forecasting.base import ForecastRequest
from services.forecasting.baseline import BaselineTimeSeriesForecastProvider
from services.ingestion.cpcb_adapter import CPCBAdapter
from services.ingestion.firms_adapter import FIRMSAdapter
from services.ingestion.imd_adapter import IMDAdapter
from services.ingestion.sentinel_adapter import Sentinel5PAdapter
from services.fusion.correlation import generate_cell_id
from services.fusion.explanation import generate_event_explanation


class EvidenceFusionEngine:
    """Core evidence fusion engine for pollution event creation, coverage tracking, and state progression."""

    # Starting prototype weights from Decision D-006
    DEFAULT_WEIGHTS = {
        "ground_sensor": 0.30,
        "satellite": 0.20,
        "citizen_report": 0.15,
        "weather": 0.15,
        "fire": 0.20,
    }

    def __init__(
        self,
        weights: Optional[Dict[str, float]] = None,
        weather_adapter: Optional[IMDAdapter] = None,
        firms_adapter: Optional[FIRMSAdapter] = None,
        sentinel_adapter: Optional[Sentinel5PAdapter] = None,
        forecast_provider: Optional[Any] = None,
        cpcb_adapter: Optional[CPCBAdapter] = None,
    ):
        self.weights = weights or self.DEFAULT_WEIGHTS.copy()
        self.weather_adapter = weather_adapter or IMDAdapter()
        self.firms_adapter = firms_adapter or FIRMSAdapter()
        self.sentinel_adapter = sentinel_adapter or Sentinel5PAdapter()
        self.forecast_provider = forecast_provider or BaselineTimeSeriesForecastProvider()
        self.cpcb_adapter = cpcb_adapter or CPCBAdapter()

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

    def determine_evidence_state(
        self,
        fusion_score: float,
        corroboration_count: int,
        citizen_analysis: Optional[CitizenImageAnalysis] = None,
        ground_anomaly_score: Optional[float] = None,
    ) -> tuple[EvidenceStatus, EventSeverity]:
        """Classify scientific/multimodal evidence status (Decision D-016)."""
        # 1. Check False Positive condition
        if citizen_analysis is not None:
            if not citizen_analysis.visible_smoke and not citizen_analysis.visible_flames:
                if ground_anomaly_score is None or ground_anomaly_score < 2.0:
                    return EvidenceStatus.FALSE_POSITIVE, EventSeverity.LOW

        # 2. State classification
        if fusion_score >= 0.75 and corroboration_count >= 2:
            status = EvidenceStatus.HIGH_CONFIDENCE
            severity = EventSeverity.HIGH if fusion_score < 0.88 else EventSeverity.CRITICAL
        elif fusion_score >= 0.50 or (corroboration_count >= 2 and fusion_score >= 0.40):
            status = EvidenceStatus.CORROBORATED
            severity = EventSeverity.MODERATE if fusion_score < 0.70 else EventSeverity.HIGH
        elif fusion_score >= 0.30 or corroboration_count >= 1:
            status = EvidenceStatus.POSSIBLE
            severity = EventSeverity.LOW if fusion_score < 0.45 else EventSeverity.MODERATE
        else:
            status = EvidenceStatus.FALSE_POSITIVE
            severity = EventSeverity.LOW

        return status, severity

    def determine_event_state(
        self,
        fusion_score: float,
        corroboration_count: int,
        citizen_analysis: Optional[CitizenImageAnalysis] = None,
        ground_anomaly_score: Optional[float] = None,
    ) -> tuple[EvidenceStatus, EventSeverity]:
        """Backward-compatible method for determine_evidence_state."""
        return self.determine_evidence_state(
            fusion_score=fusion_score,
            corroboration_count=corroboration_count,
            citizen_analysis=citizen_analysis,
            ground_anomaly_score=ground_anomaly_score,
        )

    def determine_operational_status(
        self,
        evidence_status: EvidenceStatus,
        evidence_coverage: EvidenceCoverage,
        fusion_score: float,
    ) -> OperationalStatus:
        """Determine initial operational status adhering to D-016 & D-017.

        D-017 Rule: Before automatically creating an operational alert (ALERTED),
        the system requires >= 2 independent evidence classes to be present and corroborating.
        Single source events require human review and remain DETECTED.
        """
        if evidence_status == EvidenceStatus.FALSE_POSITIVE:
            return OperationalStatus.DETECTED

        # D-017: If >= 2 independent classes available AND high/corroborated confidence
        if evidence_coverage.diversity_eligible_for_alert and fusion_score >= 0.60:
            return OperationalStatus.ALERTED

        # Otherwise, requires human review before dispatching alerts
        return OperationalStatus.DETECTED

    def get_forecast_context(
        self,
        station_id: Optional[str],
        timestamp: datetime,
    ) -> Dict[str, Any]:
        """Generate PM2.5 horizon forecast context for linked monitoring station.

        Exposes current PM2.5, +6h, +12h, +24h predictions with confidence intervals.
        Never hallucinates accuracy metrics.
        """
        if not station_id:
            return {
                "available": False,
                "reason": "No linked ground monitoring station for time-series forecasting",
            }

        try:
            # Attempt to fetch station history from adapter
            observations = self.cpcb_adapter.fetch_station_observations(
                station_id=station_id,
                start_time=timestamp.replace(hour=0, minute=0, second=0),
                end_time=timestamp,
            )
            if not observations:
                return {
                    "available": False,
                    "reason": f"No historical observations available for station '{station_id}'",
                }

            req = ForecastRequest(
                station_id=station_id,
                history=observations,
                horizon=24,
            )
            resp = self.forecast_provider.forecast(req)

            # Extract +6h, +12h, +24h
            preds = resp.predictions
            p_6 = preds[5] if len(preds) > 5 else None
            p_12 = preds[11] if len(preds) > 11 else None
            p_24 = preds[23] if len(preds) > 23 else (preds[-1] if preds else None)

            current_val = float(observations[-1].pm25) if observations[-1].pm25 is not None else None

            model_label = getattr(resp, "model_name", resp.provider_type)
            gen_at = getattr(resp, "generated_at", datetime.now(timezone.utc)).isoformat()

            return {
                "available": True,
                "current_pm25": current_val,
                "forecast_6h": p_6.pm25_forecast if p_6 else None,
                "forecast_12h": p_12.pm25_forecast if p_12 else None,
                "forecast_24h": p_24.pm25_forecast if p_24 else None,
                "interval": {
                    "lower_95": p_24.lower_bound if p_24 else None,
                    "upper_95": p_24.upper_bound if p_24 else None,
                } if p_24 else None,
                "provider_name": resp.provider_type,
                "model_name": model_label,
                "generated_at": gen_at,
            }
        except Exception as e:
            return {
                "available": False,
                "reason": f"Forecast provider execution failed: {str(e)}",
            }

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
        """Fuse all 5 evidence sources, evaluate coverage, attach forecast, and construct canonical event."""
        signals: Dict[str, EvidenceSignal] = {}

        # 1. Ground Sensor Signal
        if ground_anomaly and ground_anomaly.get("pm25") is not None:
            pm25 = float(ground_anomaly["pm25"])
            z_score = float(ground_anomaly.get("anomaly_score", 0.0))
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

        # 3. Satellite (Sentinel-5P / Earth Engine)
        sentinel_obs = self.sentinel_adapter.get_atmospheric_observation(lat, lon, timestamp)
        if sentinel_obs and (sentinel_obs.no2_tropospheric_column or sentinel_obs.aerosol_index):
            # Evaluate atmospheric burden: tropospheric NO2 > 100 or Aerosol Index > 1.5
            no2 = sentinel_obs.no2_tropospheric_column or 0.0
            ai = sentinel_obs.aerosol_index or 0.0
            sat_score = min(1.0, max(0.2, (no2 / 200.0) * 0.6 + (ai / 3.0) * 0.4))

            signals["satellite"] = EvidenceSignal(
                source="satellite",
                timestamp=sentinel_obs.timestamp,
                location={"lat": sentinel_obs.lat, "lng": sentinel_obs.lon},
                signal_type="tropospheric_no2_aerosol_index",
                score=round(sat_score, 2),
                weight=self.weights["satellite"],
                availability=True,
                metadata={
                    "no2_micromol_m2": no2,
                    "aerosol_index": ai,
                    "distance_km": sentinel_obs.distance_km,
                    "notice": "Atmospheric column density; not ground-level PM2.5 measurement",
                },
            )
        else:
            signals["satellite"] = EvidenceSignal(
                source="satellite",
                timestamp=timestamp,
                location={"lat": lat, "lng": lon},
                signal_type="tropospheric_no2_aerosol_index",
                score=None,
                weight=self.weights["satellite"],
                availability=False,
                metadata={"status": "unavailable", "note": "Sentinel-5P orbital overpass unavailable at current timestamp"},
            )

        # 4. Weather (IMD)
        imd_obs = self.weather_adapter.get_weather_observation(lat, lon, timestamp)
        if imd_obs is not None:
            # Low wind speed (<2.0 m/s) and moderate humidity impede dispersion -> elevated dispersion risk
            wind = imd_obs.wind_speed
            if wind < 1.5:
                dispersion_risk = 0.85
            elif wind < 3.0:
                dispersion_risk = 0.65
            elif wind < 5.0:
                dispersion_risk = 0.40
            else:
                dispersion_risk = 0.20

            signals["weather"] = EvidenceSignal(
                source="weather",
                timestamp=imd_obs.timestamp,
                location={"lat": imd_obs.lat, "lng": imd_obs.lon},
                signal_type="wind_dispersion_inversion_risk",
                score=round(dispersion_risk, 2),
                weight=self.weights["weather"],
                availability=True,
                metadata={
                    "station_name": imd_obs.station_name,
                    "wind_speed_ms": imd_obs.wind_speed,
                    "wind_direction_deg": imd_obs.wind_direction,
                    "temperature_c": imd_obs.temperature,
                    "humidity_pct": imd_obs.humidity,
                    "rainfall_mm": imd_obs.rainfall,
                    "distance_km": imd_obs.distance_km,
                },
            )
        else:
            signals["weather"] = EvidenceSignal(
                source="weather",
                timestamp=timestamp,
                location={"lat": lat, "lng": lon},
                signal_type="wind_dispersion_inversion_risk",
                score=None,
                weight=self.weights["weather"],
                availability=False,
                metadata={"status": "unavailable", "note": "Local meteorological station offline"},
            )

        # 5. Fire (NASA FIRMS)
        firms_obs = self.firms_adapter.get_thermal_anomaly(lat, lon, timestamp)
        if firms_obs is not None:
            # Score based on FRP and confidence
            frp = firms_obs.frp or 10.0
            conf = (firms_obs.confidence or 70.0) / 100.0
            fire_score = min(1.0, max(0.3, (frp / 30.0) * 0.6 + conf * 0.4))

            signals["fire"] = EvidenceSignal(
                source="fire",
                timestamp=firms_obs.acquisition_time,
                location={"lat": firms_obs.latitude, "lng": firms_obs.longitude},
                signal_type="thermal_anomaly",
                score=round(fire_score, 2),
                weight=self.weights["fire"],
                availability=True,
                metadata={
                    "claim_statement": firms_obs.claim_statement,
                    "satellite": firms_obs.satellite_source,
                    "confidence": firms_obs.confidence,
                    "frp_mw": firms_obs.frp,
                    "distance_km": firms_obs.distance_km,
                },
            )
        else:
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

        # Classify evidence state (Decision D-016)
        evidence_status, severity = self.determine_evidence_state(
            fusion_score=fusion_score,
            corroboration_count=corrob_count,
            citizen_analysis=citizen_analysis,
            ground_anomaly_score=ground_anomaly.get("anomaly_score") if ground_anomaly else None,
        )

        # Compute evidence coverage
        ground_avail = bool(signals["ground_sensor"].availability)
        cit_avail = bool(signals["citizen_report"].availability)
        sat_avail = bool(signals["satellite"].availability)
        wx_avail = bool(signals["weather"].availability)
        fire_avail = bool(signals["fire"].availability)

        diversity_eligible = avail_count >= 2 and corrob_count >= 2

        evidence_coverage = EvidenceCoverage(
            ground_sensor=ground_avail,
            citizen_report=cit_avail,
            satellite=sat_avail,
            weather=wx_avail,
            fire=fire_avail,
            available_count=avail_count,
            total_sources=5,
            coverage_ratio=round(avail_count / 5.0, 2),
            diversity_eligible_for_alert=diversity_eligible,
        )

        # Determine initial operational status (Decision D-016 & D-017)
        operational_status = self.determine_operational_status(
            evidence_status=evidence_status,
            evidence_coverage=evidence_coverage,
            fusion_score=fusion_score,
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
        elif firms_obs is not None:
            probable_source = "Nearby fire/thermal anomaly detected"
        elif ground_anomaly and ground_anomaly.get("pm25"):
            probable_source = "Unspecified particulate elevation"

        # Generate transparent human explanation
        explanation = generate_event_explanation(
            signals=signals,
            fusion_score=fusion_score,
            status=evidence_status,
            severity=severity,
            probable_source=probable_source,
            corroboration_count=corrob_count,
        )

        # Query forecast context
        active_station = station_id or (ground_anomaly.get("station_id") if ground_anomaly else None)
        forecast_context = self.get_forecast_context(active_station, timestamp)

        cell_id = generate_cell_id(lat, lon)
        location = LocationCell(lat=lat, lng=lon, cell_id=cell_id)

        evidence_breakdown = EvidenceBreakdown(
            signals=signals,
            fusion_score=fusion_score,
            available_weight_sum=avail_weight,
            available_sources_count=avail_count,
            corroborating_sources_count=corrob_count,
            explanation_text=explanation,
        )

        # Update existing or create new
        if existing_event:
            existing_event.timestamp = timestamp
            existing_event.evidence_status = evidence_status
            existing_event.status = evidence_status  # alias
            existing_event.severity = severity
            existing_event.evidence = evidence_breakdown
            existing_event.evidence_coverage = evidence_coverage
            existing_event.forecast = forecast_context
            if probable_source and not existing_event.probable_source:
                existing_event.probable_source = probable_source
            if report_id and report_id not in existing_event.report_ids:
                existing_event.report_ids.append(report_id)
            if station_id and station_id not in existing_event.station_ids:
                existing_event.station_ids.append(station_id)
            return existing_event

        report_ids_list = [report_id] if report_id else []
        station_ids_list = [station_id] if station_id else []
        if ground_anomaly and ground_anomaly.get("station_id"):
            st_id = ground_anomaly["station_id"]
            if st_id not in station_ids_list:
                station_ids_list.append(st_id)

        event = PollutionEvent(
            location=location,
            evidence_status=evidence_status,
            operational_status=operational_status,
            status=evidence_status,
            severity=severity,
            evidence=evidence_breakdown,
            evidence_coverage=evidence_coverage,
            forecast=forecast_context,
            probable_source=probable_source,
            human_verification_required=citizen_analysis.needs_human_verification if citizen_analysis else True,
            report_ids=report_ids_list,
            station_ids=station_ids_list,
        )
        return event
