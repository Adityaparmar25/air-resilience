"""Canonical monitoring schema for Air Resilience Network.

Strictly implements the monitoring observation schema agreed in architecture.md Section 10.
"""

from datetime import datetime, timezone, timedelta
from typing import Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class MonitoringObservation(BaseModel):
    """Canonical ground monitoring observation schema.

    Represents an ambient air-quality observation from CPCB or affiliated monitoring stations.
    Missing pollutant measurements MUST remain None/null and must never be converted to zero.
    """

    station_id: str = Field(
        ...,
        min_length=1,
        description="Unique monitoring station identifier (e.g. 'DL001', 'site_101')",
    )
    station_name: str = Field(
        ...,
        min_length=1,
        description="Human-readable station name (e.g. 'Anand Vihar, Delhi')",
    )
    timestamp: datetime = Field(
        ...,
        description="Observation timestamp (UTC-normalized datetime)",
    )
    lat: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="Station latitude in decimal degrees (-90.0 to 90.0)",
    )
    lon: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="Station longitude in decimal degrees (-180.0 to 180.0)",
    )
    city: str = Field(
        ...,
        min_length=1,
        description="City where the monitoring station is located",
    )
    state: str = Field(
        ...,
        min_length=1,
        description="State/UT where the monitoring station is located",
    )

    # Nullable pollutant fields (concentrations in ug/m3, CO in mg/m3 per CPCB norms)
    pm25: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=2000.0,
        description="Particulate Matter 2.5 concentration in ug/m3 (>= 0, null if unmeasured)",
    )
    pm10: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=3000.0,
        description="Particulate Matter 10 concentration in ug/m3 (>= 0, null if unmeasured)",
    )
    no2: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1500.0,
        description="Nitrogen Dioxide concentration in ug/m3 (>= 0, null if unmeasured)",
    )
    so2: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1500.0,
        description="Sulfur Dioxide concentration in ug/m3 (>= 0, null if unmeasured)",
    )
    co: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Carbon Monoxide concentration in mg/m3 (>= 0, null if unmeasured)",
    )
    o3: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1000.0,
        description="Ozone concentration in ug/m3 (>= 0, null if unmeasured)",
    )

    @field_validator("timestamp")
    @classmethod
    def ensure_utc_and_not_future(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware (normalized to UTC) and not impossibly in future."""
        if v.tzinfo is None:
            # Assume UTC if naive
            v = v.replace(tzinfo=timezone.utc)
        else:
            v = v.astimezone(timezone.utc)

        # Allow max 15 minutes clock drift into future
        max_future = datetime.now(timezone.utc) + timedelta(minutes=15)
        if v > max_future:
            raise ValueError(f"Observation timestamp cannot be in the future: {v.isoformat()}")
        return v

    @model_validator(mode="after")
    def validate_non_empty_identity(self) -> "MonitoringObservation":
        """Validate that identifiers and locations are stripped of whitespace."""
        if not self.station_id.strip():
            raise ValueError("station_id must not be empty or whitespace")
        if not self.station_name.strip():
            raise ValueError("station_name must not be empty or whitespace")
        if not self.city.strip():
            raise ValueError("city must not be empty or whitespace")
        if not self.state.strip():
            raise ValueError("state must not be empty or whitespace")
        return self
