"""Schemas for Citizen Reports and Observation Submissions."""

from datetime import datetime, timezone
from typing import Optional
import uuid
from pydantic import BaseModel, Field, field_validator

from schemas.citizen_image_analysis import CitizenImageAnalysis


class ReportSubmissionRequest(BaseModel):
    """Schema for submitting a citizen report (JSON payload alternative to multipart)."""

    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude of observation")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude of observation")
    timestamp: Optional[datetime] = Field(
        default=None,
        description="Observation timestamp (UTC). Defaults to current time if omitted.",
    )
    description: Optional[str] = Field(
        default=None,
        max_length=500,
        description="Optional brief observation description from the reporter",
    )
    image_base64: Optional[str] = Field(
        default=None,
        description="Optional Base64-encoded image string",
    )

    @field_validator("timestamp")
    @classmethod
    def default_utc_now(cls, v: Optional[datetime]) -> datetime:
        if v is None:
            return datetime.now(timezone.utc)
        if v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v.astimezone(timezone.utc)


class CitizenReport(BaseModel):
    """Operational internal record for a citizen report."""

    report_id: str = Field(default_factory=lambda: f"rep_{uuid.uuid4().hex[:10]}")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    description: Optional[str] = None
    image_path: Optional[str] = None
    has_image: bool = False
    status: str = Field(
        default="PENDING_ANALYSIS",
        description="PENDING_ANALYSIS | ANALYZED | CORRELATED | FALSE_POSITIVE",
    )
    analysis: Optional[CitizenImageAnalysis] = None
    event_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ReportResponse(BaseModel):
    """API response model for citizen report submission and status retrieval."""

    report_id: str
    timestamp: datetime
    lat: float
    lon: float
    description: Optional[str] = None
    has_image: bool
    status: str
    analysis: Optional[CitizenImageAnalysis] = None
    event_id: Optional[str] = None
