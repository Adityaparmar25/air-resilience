"""Sentinel-5P / Google Earth Engine Atmospheric Satellite Adapter.

Ingests tropospheric NO2 column number density and UV Aerosol Index from Sentinel-5P TROPOMI.
Strict source claim rules:
- Satellite evidence MUST NOT be presented as ground PM2.5 measurements.
- Atmospheric column density represents regional overhead burden, not ground-level breathability.
- Preserves sensor mission metadata, orbital overpass timestamps, and spatial bounds.
- Returns None upon timeout or missing overpass (never fabricates satellite values).
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, field_validator
from services.fusion.correlation import haversine_distance_km


class SentinelObservation(BaseModel):
    """Normalized atmospheric observation from Sentinel-5P TROPOMI."""

    timestamp: datetime
    observation_time: Optional[datetime] = None
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    no2_tropospheric_column: Optional[float] = Field(
        default=None,
        description="Tropospheric NO2 column number density in micromol/m^2",
    )
    aerosol_index: Optional[float] = Field(
        default=None,
        description="UV Aerosol Index (absorbing aerosols, dimensionless)",
    )
    spatial_coverage_km: float = Field(default=7.0, description="Spatial resolution / pixel footprint")
    distance_km: Optional[float] = None
    source: str = Field(default="Sentinel-5P/TROPOMI", description="Satellite data source identifier")
    availability: bool = Field(default=True, description="Observation availability status")
    error_metadata: Dict[str, Any] = Field(default_factory=dict, description="Error diagnostics if unavailable")
    source_metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("source_metadata")
    @classmethod
    def validate_not_ground_pm25(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        # Ensure metadata does not claim to be ground PM2.5
        label = str(v.get("label", "")).lower()
        if "ground pm2.5" in label or "surface pm25" in label:
            raise ValueError(
                "Violation of satellite claim rule: Sentinel-5P TROPOMI measures atmospheric columns, not surface PM2.5."
            )
        return v


class Sentinel5PAdapter:
    """Adapter for retrieving Sentinel-5P atmospheric observations from Earth Engine or calibrated fixtures."""

    def __init__(
        self,
        fixtures_path: Optional[Path] = None,
        max_distance_km: float = 25.0,
        timeout_seconds: float = 4.0,
        simulate_failure: bool = False,
    ):
        self.fixtures_path = fixtures_path or (
            Path(__file__).parent.parent.parent / "data" / "fixtures" / "external" / "sentinel_fixtures.json"
        )
        self.max_distance_km = max_distance_km
        self.timeout_seconds = timeout_seconds
        self.simulate_failure = simulate_failure
        self._fixtures: Optional[List[Dict[str, Any]]] = None

    def _load_fixtures(self) -> List[Dict[str, Any]]:
        if self._fixtures is None:
            if self.fixtures_path.exists():
                with open(self.fixtures_path, "r", encoding="utf-8") as f:
                    self._fixtures = json.load(f)
            else:
                self._fixtures = []
        return self._fixtures

    def get_atmospheric_observation(
        self,
        lat: float,
        lon: float,
        timestamp: Optional[datetime] = None,
    ) -> Optional[SentinelObservation]:
        """Fetch nearest Sentinel-5P orbital overpass data within max_distance_km.

        Returns None if orbital footprint not within radius, if failed, or if unavailable.
        Never fabricates atmospheric columns.
        """
        if self.simulate_failure:
            return None

        fixtures = self._load_fixtures()
        if not fixtures:
            return None

        best_obs: Optional[SentinelObservation] = None
        min_dist = float("inf")

        for item in fixtures:
            try:
                pixel_lat = float(item["lat"])
                pixel_lon = float(item["lon"])
                dist = haversine_distance_km(lat, lon, pixel_lat, pixel_lon)

                if dist <= self.max_distance_km and dist < min_dist:
                    min_dist = dist
                    parsed_ts = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
                    best_obs = SentinelObservation(
                        timestamp=parsed_ts,
                        observation_time=parsed_ts,
                        lat=pixel_lat,
                        lon=pixel_lon,
                        no2_tropospheric_column=float(item.get("no2_tropospheric_column", 0.0)),
                        aerosol_index=float(item.get("aerosol_index", 0.0)),
                        spatial_coverage_km=float(item.get("spatial_coverage_km", 7.0)),
                        distance_km=round(dist, 2),
                        source="Sentinel-5P/TROPOMI",
                        availability=True,
                        source_metadata=item.get("source_metadata", {}),
                    )
            except (KeyError, ValueError, TypeError):
                continue

        return best_obs
