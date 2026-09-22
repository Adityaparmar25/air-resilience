import base64
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, File, Form, HTTPException, Query, Request, UploadFile, status
from pydantic import BaseModel, Field

from apps.api.config import get_settings
from schemas.api import (
    AnomalyRequest,
    AnomalyResponse,
    HealthResponse,
    StationSeriesResponse,
)
from schemas.canonical import MonitoringObservation
from schemas.event import EventStatus, EvidenceStatus, OperationalStatus, PollutionEvent
from schemas.incident import (
    AcknowledgeIncidentRequest,
    AddNoteRequest,
    AssignIncidentRequest,
    AuditRecord,
    CreateIncidentRequest,
    DismissIncidentRequest,
    Incident,
    IncidentNote,
    IncidentPriority,
    IncidentStatus,
    InvestigateIncidentRequest,
    ResolveIncidentRequest,
)
from schemas.report import CitizenReport, ReportResponse, ReportSubmissionRequest
from services.ai.gemini_service import GeminiVisionAnalyzer
from services.anomaly.detector import (
    AnomalyDetectionConfig,
    ExplainableAnomalyDetector,
)
from services.forecasting.base import (
    ForecastRequest,
    ForecastResponse,
)
from services.forecasting.baseline import BaselineTimeSeriesForecastProvider
from services.forecasting.time_series_service import TimeSeriesService
from services.fusion.correlation import SpatioTemporalCorrelationService
from services.fusion.engine import EvidenceFusionEngine
from services.ingestion.cpcb_adapter import CPCBAdapter
from services.ingestion.quality_pipeline import DataQualityPipeline
from services.operational.store import get_operational_store

router = APIRouter()

# Directories for data storage
FIXTURE_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "fixtures"
UPLOADS_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/health", response_model=HealthResponse, tags=["System"])
def health_check() -> HealthResponse:
    """System health check endpoint."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service="air-resilience-api",
        version="0.1.0",
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
    )


@router.get(
    "/api/v1/stations/{station_id}/series",
    response_model=StationSeriesResponse,
    tags=["Monitoring"],
    responses={
        404: {"description": "Station not found in monitoring network or fixtures"},
    },
)
def get_station_series(
    station_id: str,
    limit: int = Query(default=48, ge=1, le=168, description="Maximum observations to return"),
    scenario: Optional[str] = Query(
        default=None,
        description="Optional fixture scenario: 'normal' | 'elevated' | 'missing' | 'spike'",
    ),
) -> StationSeriesResponse:
    """Retrieve chronologically ordered time series and quality checks for a monitoring station."""
    # Determine fixture source based on scenario or default normal series
    scenario_files = {
        "normal": "normal_series.json",
        "elevated": "elevated_series.json",
        "missing": "missing_observations.json",
        "spike": "suspicious_spike.json",
    }
    fixture_file = scenario_files.get(scenario or "normal", "normal_series.json")
    fixture_path = FIXTURE_DIR / fixture_file

    if not fixture_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Development fixture file missing: {fixture_path}",
        )

    adapter = CPCBAdapter(default_fixture_path=str(fixture_path))
    pipeline = DataQualityPipeline(adapter=adapter)

    # Fetch raw observations for station
    raw_records = adapter.fetch(station_id=station_id, is_fixture=True)
    if not raw_records:
        # Check if station exists in station registry
        if station_id.upper() in CPCBAdapter.STATION_REGISTRY:
            # If in registry but no observations in this specific scenario file
            raw_records = adapter.fetch(is_fixture=True)
            # Filter if station matches
            raw_records = [
                r for r in raw_records
                if str(adapter._extract_first_match(r, adapter.STATION_ID_KEYS) or "").upper()
                == station_id.upper()
            ]

    if not raw_records:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Station '{station_id}' not found in active observations or fixtures",
        )

    # Process batch through data quality pipeline
    quality_records = pipeline.process_batch(raw_records, is_fixture=True)
    observations = [qr.observation for qr in quality_records]

    # Chronological sort and limit
    sorted_obs = TimeSeriesService.sort_chronological(observations, ascending=True)
    recent_obs = sorted_obs[-limit:] if len(sorted_obs) > limit else sorted_obs

    # Baseline and gaps calculation
    baseline = TimeSeriesService.compute_local_baseline(recent_obs)
    gaps = TimeSeriesService.detect_missing_timestamps(recent_obs)

    # Quality flags aggregation
    all_flags: List[str] = []
    for qr in quality_records:
        all_flags.extend([f.value for f in qr.flags])
    flag_counts = dict(Counter(all_flags))

    station_name = recent_obs[0].station_name if recent_obs else station_id

    return StationSeriesResponse(
        station_id=station_id,
        station_name=station_name,
        observation_count=len(recent_obs),
        observations=recent_obs,
        baseline=baseline,
        gaps_detected=gaps,
        quality_flags_summary=flag_counts,
        data_source="fixture",
    )


@router.post(
    "/api/v1/anomaly",
    response_model=AnomalyResponse,
    tags=["ML & Analytics"],
    responses={
        422: {"description": "Validation error: PM2.5 measurement is null"},
    },
)
def detect_anomaly(request: AnomalyRequest) -> AnomalyResponse:
    """Evaluate target observation against historical baseline for explainable anomaly detection."""
    if request.observation.pm25 is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Cannot detect anomaly: observation pm25 measurement is null/unavailable",
        )

    detector = ExplainableAnomalyDetector()
    try:
        result = detector.detect(
            observation=request.observation,
            history=request.history,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    return AnomalyResponse(
        station_id=result.station_id,
        timestamp=result.timestamp,
        pm25=result.pm25,
        expected_pm25=result.expected_pm25,
        anomaly_score=result.anomaly_score,
        status=result.status,
        explanation=result.explanation,
        baseline_std=result.baseline_std,
    )


@router.post(
    "/api/v1/forecast",
    response_model=ForecastResponse,
    tags=["ML & Analytics"],
    responses={
        400: {"description": "History does not contain observations for specified station"},
        422: {"description": "Invalid horizon or empty history"},
    },
)
def generate_forecast(request: ForecastRequest) -> ForecastResponse:
    """Produce PM2.5 horizon forecast using the forecast provider abstraction."""
    provider = BaselineTimeSeriesForecastProvider()
    try:
        response = provider.forecast(request)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return response


# ==============================================================================
# Phase 3B — Citizen Reports, Gemini Multimodal Analysis, and Evidence Fusion
# ==============================================================================

class DetectEventRequest(BaseModel):
    """Request model for event detection and evidence fusion."""

    report_id: Optional[str] = Field(default=None, description="Optional citizen report ID to correlate")
    station_id: Optional[str] = Field(default=None, description="Optional ground station ID to correlate")
    lat: Optional[float] = Field(default=None, ge=-90.0, le=90.0, description="Latitude for spatial query")
    lon: Optional[float] = Field(default=None, ge=-180.0, le=180.0, description="Longitude for spatial query")
    timestamp: Optional[datetime] = Field(default=None, description="Timestamp of observation (UTC)")


@router.post(
    "/api/v1/reports",
    response_model=ReportResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Citizen Reports"],
    summary="Submit citizen pollution report with optional photograph",
)
async def submit_citizen_report(
    request: Request,
    file: Optional[UploadFile] = File(None),
    lat: Optional[float] = Form(None),
    lon: Optional[float] = Form(None),
    description: Optional[str] = Form(None),
) -> ReportResponse:
    """Submit a citizen report with optional photographic evidence.

    Accepts both multipart/form-data with file upload or application/json payload.
    Enforces upload validation: file size limit (10MB) and allowed image MIME types.
    """
    store = get_operational_store()
    saved_image_path: Optional[str] = None
    has_image = False

    # Check if request was submitted as application/json
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body_dict = await request.json()
            req = ReportSubmissionRequest.model_validate(body_dict)
            lat = req.lat
            lon = req.lon
            description = req.description
            obs_timestamp = req.timestamp or datetime.now(timezone.utc)

            if req.image_base64:
                # Decode Base64 image
                image_data = base64.b64decode(req.image_base64)
                if len(image_data) > 10 * 1024 * 1024:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Image payload exceeds 10MB limit",
                    )
                report_file_name = f"report_json_{int(obs_timestamp.timestamp())}.jpg"
                saved_image_path = str(UPLOADS_DIR / report_file_name)
                with open(saved_image_path, "wb") as f:
                    f.write(image_data)
                has_image = True

        except Exception as e:
            if isinstance(e, HTTPException):
                raise e
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid JSON report payload: {e}",
            )
    else:
        # Multipart form submission
        if lat is None or lon is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Coordinates (lat and lon) are required in submission form",
            )
        obs_timestamp = datetime.now(timezone.utc)

        if file and file.filename:
            allowed_types = {"image/jpeg", "image/png", "image/webp", "image/jpg"}
            if file.content_type and file.content_type.lower() not in allowed_types:
                raise HTTPException(
                    status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                    detail=f"Unsupported file type '{file.content_type}'. Allowed types: JPEG, PNG, WebP.",
                )

            contents = await file.read()
            if len(contents) > 10 * 1024 * 1024:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Uploaded image exceeds 10MB size limit",
                )

            safe_filename = f"report_{int(obs_timestamp.timestamp())}_{file.filename}"
            saved_image_path = str(UPLOADS_DIR / safe_filename)
            with open(saved_image_path, "wb") as f:
                f.write(contents)
            has_image = True

    report = CitizenReport(
        lat=lat,
        lon=lon,
        timestamp=obs_timestamp,
        description=description,
        image_path=saved_image_path,
        has_image=has_image,
        status="PENDING_ANALYSIS",
    )
    store.save_report(report)

    return ReportResponse(
        report_id=report.report_id,
        timestamp=report.timestamp,
        lat=report.lat,
        lon=report.lon,
        description=report.description,
        has_image=report.has_image,
        status=report.status,
        analysis=report.analysis,
        event_id=report.event_id,
    )


@router.post(
    "/api/v1/reports/{report_id}/analyze",
    response_model=ReportResponse,
    tags=["Citizen Reports"],
    summary="Execute Gemini multimodal vision analysis on submitted citizen report photograph",
)
def analyze_citizen_report(report_id: str) -> ReportResponse:
    """Analyze citizen report photograph using Gemini Vision.

    Validates output through strict schema and security guardrails.
    Rejects hallucinations, company accusations, or invented PM2.5 numbers.
    """
    store = get_operational_store()
    report = store.get_report(report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Citizen report '{report_id}' not found",
        )

    if not report.has_image or not report.image_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Report '{report_id}' has no photograph attached to analyze",
        )

    image_file = Path(report.image_path)
    if not image_file.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Associated image file not found on disk: {report.image_path}",
        )

    analyzer = GeminiVisionAnalyzer()
    try:
        analysis = analyzer.analyze_image(
            image_data=image_file,
            filename=image_file.name,
            context_description=report.description,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Gemini image analysis failed or violated security guardrails: {e}",
        )

    report.analysis = analysis
    report.status = "ANALYZED"
    store.save_report(report)

    return ReportResponse(
        report_id=report.report_id,
        timestamp=report.timestamp,
        lat=report.lat,
        lon=report.lon,
        description=report.description,
        has_image=report.has_image,
        status=report.status,
        analysis=report.analysis,
        event_id=report.event_id,
    )


@router.post(
    "/api/v1/events/detect",
    response_model=PollutionEvent,
    tags=["Event Engine"],
    summary="Execute spatio-temporal correlation and multi-source evidence fusion",
)
def detect_and_fuse_event(request: DetectEventRequest) -> PollutionEvent:
    """Correlate available signals, execute evidence fusion, and create/update PollutionEvent.

    Applies Decision D-006 evidence weights and D-007 missing data policy.
    Prevents duplicate event creation when multiple reports describe the same incident.
    """
    store = get_operational_store()
    fusion_engine = EvidenceFusionEngine()

    citizen_analysis: Optional[CitizenImageAnalysis] = None
    target_lat = request.lat
    target_lon = request.lon
    target_timestamp = request.timestamp or datetime.now(timezone.utc)
    target_report_id = request.report_id

    # 1. If report_id supplied, load and prepare report data
    if target_report_id:
        report = store.get_report(target_report_id)
        if not report:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Citizen report '{target_report_id}' not found",
            )
        target_lat = report.lat
        target_lon = report.lon
        target_timestamp = report.timestamp

        # Auto-analyze if report has image but was not yet analyzed
        if report.analysis:
            citizen_analysis = report.analysis
        elif report.has_image and report.image_path:
            analyzer = GeminiVisionAnalyzer()
            citizen_analysis = analyzer.analyze_image(
                image_data=Path(report.image_path),
                context_description=report.description,
            )
            report.analysis = citizen_analysis
            report.status = "ANALYZED"
            store.save_report(report)

    if target_lat is None or target_lon is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Coordinates (lat and lon) or a valid report_id must be provided for event detection",
        )

    # 2. Correlate with nearby ground monitoring stations
    nearby_stations = SpatioTemporalCorrelationService.find_nearby_stations(target_lat, target_lon, max_distance_km=15.0)
    ground_anomaly_info: Optional[Dict[str, Any]] = None
    matched_station_id: Optional[str] = None

    if nearby_stations:
        nearest_station_id, nearest_info, distance_km = nearby_stations[0]
        matched_station_id = nearest_station_id

        # Load station observations from normal or elevated fixture to compute anomaly
        # In elevated scenarios or when citizen reports heavy smoke, check elevated fixture
        fixture_file = "elevated_series.json" if (citizen_analysis and citizen_analysis.visible_smoke) else "normal_series.json"
        fixture_path = FIXTURE_DIR / fixture_file

        if fixture_path.exists():
            adapter = CPCBAdapter(default_fixture_path=str(fixture_path))
            pipeline = DataQualityPipeline(adapter=adapter)
            raw_obs = adapter.fetch(station_id=nearest_station_id, is_fixture=True)
            if not raw_obs:
                raw_obs = adapter.fetch(is_fixture=True)

            if raw_obs:
                quality_recs = pipeline.process_batch(raw_obs, is_fixture=True)
                observations = [qr.observation for qr in quality_recs]
                sorted_obs = TimeSeriesService.sort_chronological(observations, ascending=True)

                if sorted_obs:
                    detector = ExplainableAnomalyDetector()
                    target_obs = sorted_obs[-1]
                    history_obs = sorted_obs[:-1]
                    anomaly_res = detector.detect(target_obs, history_obs)

                    ground_anomaly_info = {
                        "station_id": nearest_station_id,
                        "station_name": nearest_info.get("name", nearest_station_id),
                        "pm25": anomaly_res.pm25,
                        "expected_pm25": anomaly_res.expected_pm25,
                        "anomaly_score": anomaly_res.anomaly_score,
                        "status": anomaly_res.status.value,
                        "distance_km": distance_km,
                        "timestamp": target_obs.timestamp,
                    }

    # 3. Check for matching active event to prevent duplication
    active_events = store.list_events()
    matched_event_match = SpatioTemporalCorrelationService.find_matching_event(
        lat=target_lat,
        lon=target_lon,
        timestamp=target_timestamp,
        active_events=active_events,
        spatial_radius_km=5.0,
        temporal_window_hours=3.0,
    )

    existing_event = matched_event_match[0] if matched_event_match else None

    # 4. Fuse evidence and create/update event
    event = fusion_engine.create_or_update_event(
        lat=target_lat,
        lon=target_lon,
        timestamp=target_timestamp,
        citizen_analysis=citizen_analysis,
        ground_anomaly=ground_anomaly_info,
        existing_event=existing_event,
        report_id=target_report_id,
        station_id=matched_station_id,
    )

    # Save event
    store.save_event(event)

    # Link report if present
    if target_report_id:
        report = store.get_report(target_report_id)
        if report:
            report.event_id = event.event_id
            report.status = "CORRELATED"
            store.save_report(report)

    return event


@router.get(
    "/api/v1/events",
    response_model=List[PollutionEvent],
    tags=["Event Engine"],
    summary="List active pollution events with optional status filter",
)
def list_pollution_events(
    status: Optional[EventStatus] = Query(default=None, description="Optional status filter"),
    limit: int = Query(default=50, ge=1, le=100, description="Max events to return"),
) -> List[PollutionEvent]:
    """Retrieve list of tracked pollution events sorted by timestamp descending."""
    store = get_operational_store()
    return store.list_events(status=status, limit=limit)


@router.get(
    "/api/v1/events/{event_id}",
    response_model=PollutionEvent,
    tags=["Event Engine"],
    summary="Retrieve detailed pollution event and complete evidence breakdown",
)
def get_pollution_event(event_id: str) -> PollutionEvent:
    """Retrieve detailed pollution event by ID, including evidence signals and explanation."""
    store = get_operational_store()
    event = store.get_event(event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Pollution event '{event_id}' not found",
        )
    return event


@router.get("/api/v1/health", response_model=HealthResponse, tags=["System"])
def api_health_check() -> HealthResponse:
    """API versioned health check endpoint."""
    return health_check()


# =============================================================================
# AUTHORITY INCIDENT WORKFLOW & AUDIT APIS (PHASE 3C)
# =============================================================================

@router.post(
    "/api/v1/incidents",
    response_model=Incident,
    status_code=status.HTTP_201_CREATED,
    tags=["Authority Incidents"],
    summary="Create authority incident from corroborated pollution event",
)
def create_incident(request: CreateIncidentRequest) -> Incident:
    """Create authority incident from verified pollution event.

    Enforces D-017 minimum evidence diversity:
    Events with >= 2 independent evidence sources escalate to ALERTED.
    Single-source events default to DETECTED (requiring human review).
    """
    store = get_operational_store()
    event = store.get_event(request.event_id)
    if not event:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Originating pollution event '{request.event_id}' not found",
        )

    incident = store.create_incident(request, event)
    return incident


@router.get(
    "/api/v1/incidents",
    response_model=List[Incident],
    tags=["Authority Incidents"],
    summary="List authority incidents with status and priority filters",
)
def list_incidents(
    status: Optional[IncidentStatus] = Query(default=None, description="Filter by operational status"),
    priority: Optional[IncidentPriority] = Query(default=None, description="Filter by priority"),
    limit: int = Query(default=50, ge=1, le=100, description="Max incidents to return"),
) -> List[Incident]:
    """Retrieve tracked authority incidents sorted by creation timestamp descending."""
    store = get_operational_store()
    return store.list_incidents(status=status, priority=priority, limit=limit)


@router.get(
    "/api/v1/incidents/{incident_id}",
    response_model=Incident,
    tags=["Authority Incidents"],
    summary="Retrieve authority incident detail",
)
def get_incident(incident_id: str) -> Incident:
    """Retrieve incident by ID."""
    store = get_operational_store()
    incident = store.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return incident


@router.post(
    "/api/v1/incidents/{incident_id}/assign",
    response_model=Incident,
    tags=["Authority Incidents"],
    summary="Assign incident to response unit",
)
def assign_incident(incident_id: str, request: AssignIncidentRequest) -> Incident:
    """Assign incident to field officer / team. Transition to ASSIGNED."""
    store = get_operational_store()
    try:
        return store.assign_incident(incident_id, request)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/api/v1/incidents/{incident_id}/acknowledge",
    response_model=Incident,
    tags=["Authority Incidents"],
    summary="Acknowledge incident by field responder",
)
def acknowledge_incident(incident_id: str, request: AcknowledgeIncidentRequest) -> Incident:
    """Acknowledge incident. Transition to ACKNOWLEDGED."""
    store = get_operational_store()
    try:
        return store.acknowledge_incident(incident_id, request)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/api/v1/incidents/{incident_id}/investigate",
    response_model=Incident,
    tags=["Authority Incidents"],
    summary="Mark incident as actively investigating",
)
def investigate_incident(incident_id: str, request: InvestigateIncidentRequest) -> Incident:
    """Mark incident under active investigation. Transition to INVESTIGATING."""
    store = get_operational_store()
    try:
        return store.investigate_incident(incident_id, request)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/api/v1/incidents/{incident_id}/resolve",
    response_model=Incident,
    tags=["Authority Incidents"],
    summary="Resolve incident with summary",
)
def resolve_incident(incident_id: str, request: ResolveIncidentRequest) -> Incident:
    """Resolve incident. Transition to RESOLVED."""
    store = get_operational_store()
    try:
        return store.resolve_incident(incident_id, request)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/api/v1/incidents/{incident_id}/dismiss",
    response_model=Incident,
    tags=["Authority Incidents"],
    summary="Dismiss incident as false positive or non-actionable",
)
def dismiss_incident(incident_id: str, request: DismissIncidentRequest) -> Incident:
    """Dismiss incident. Transition to DISMISSED."""
    store = get_operational_store()
    try:
        return store.dismiss_incident(incident_id, request)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found")
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post(
    "/api/v1/incidents/{incident_id}/notes",
    response_model=IncidentNote,
    tags=["Authority Incidents"],
    summary="Add operational field note to incident",
)
def add_incident_note(incident_id: str, request: AddNoteRequest) -> IncidentNote:
    """Append a field note to an active incident."""
    store = get_operational_store()
    try:
        return store.add_note(incident_id, request)
    except KeyError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Incident '{incident_id}' not found")


@router.get(
    "/api/v1/incidents/{incident_id}/audit",
    response_model=List[AuditRecord],
    tags=["Authority Incidents"],
    summary="Retrieve immutable audit log for incident",
)
def get_incident_audit_log(incident_id: str) -> List[AuditRecord]:
    """Retrieve complete audit history for this incident. Audit records cannot be modified."""
    store = get_operational_store()
    incident = store.get_incident(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident '{incident_id}' not found",
        )
    return store.get_audit_records(incident_id=incident_id)

