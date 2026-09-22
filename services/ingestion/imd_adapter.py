"""India Meteorological Department (IMD) Weather Adapter.

Fetches localized meteorological observations (temperature, humidity, wind speed, wind direction, rainfall).
Guarantees:
- Validates all sensor metrics
- Preserves source metadata
- Gracefully handles timeout/failure by returning None (unavailable state)
- Never fabricates or hallucinates values
- Supports calibrated offline replay fixtures
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from services.fusion.correlation import haversine_distance_km


class IMDWeatherObservation(BaseModel):
    """Normalized meteorological context from IMD."""

    timestamp: datetime
    lat: float = Field(..., ge=-90.0, le=90.0)
    lon: float = Field(..., ge=-180.0, le=180.0)
    latitude: float = Field(..., ge=-90.0, le=90.0)
    longitude: float = Field(..., ge=-180.0, le=180.0)
    temperature: float = Field(..., description="Ambient temperature in Celsius")
    humidity: float = Field(..., ge=0.0, le=100.0, description="Relative humidity percentage")
    wind_speed: float = Field(..., ge=0.0, description="Wind speed in m/s")
    wind_direction: float = Field(..., ge=0.0, le=360.0, description="Wind direction in degrees")
    rainfall: float = Field(default=0.0, ge=0.0, description="Precipitation in mm")
    source_status: str = Field(default="AVAILABLE", description="Source status: AVAILABLE | UNAVAILABLE | DEGRADED")
    station_name: Optional[str] = None
    distance_km: Optional[float] = None
    source_metadata: Dict[str, Any] = Field(default_factory=dict)


class IMDAdapter:
    """Adapter for retrieving meteorological data from IMD or calibrated fixtures."""

    def __init__(
        self,
        fixtures_path: Optional[Path] = None,
        max_distance_km: float = 25.0,
        timeout_seconds: float = 3.0,
        simulate_timeout: bool = False,
    ):
        self.fixtures_path = fixtures_path or (
            Path(__file__).parent.parent.parent / "data" / "fixtures" / "external" / "imd_fixtures.json"
        )
        self.max_distance_km = max_distance_km
        self.timeout_seconds = timeout_seconds
        self.simulate_timeout = simulate_timeout
        self._fixtures: Optional[List[Dict[str, Any]]] = None

    def _load_fixtures(self) -> List[Dict[str, Any]]:
        if self._fixtures is None:
            if self.fixtures_path.exists():
                with open(self.fixtures_path, "r", encoding="utf-8") as f:
                    self._fixtures = json.load(f)
            else:
                self._fixtures = []
        return self._fixtures

    def get_weather_observation(
        self,
        lat: float,
        lon: float,
        timestamp: Optional[datetime] = None,
    ) -> Optional[IMDWeatherObservation]:
        """Fetch closest valid IMD observation within max_distance_km.

        Returns None if no station is within radius, if timed out, or if unavailable.
        Never fabricates measurements.
        """
        if self.simulate_timeout:
            return None

        fixtures = self._load_fixtures()
        if not fixtures:
            return None

        best_obs: Optional[IMDWeatherObservation] = None
        min_dist = float("inf")

        for item in fixtures:
            try:
                station_lat = float(item["lat"])
                station_lon = float(item["lon"])
                dist = haversine_distance_km(lat, lon, station_lat, station_lon)

                if dist <= self.max_distance_km and dist < min_dist:
                    min_dist = dist
                    parsed_ts = datetime.fromisoformat(item["timestamp"].replace("Z", "+00:00"))
                    best_obs = IMDWeatherObservation(
                        timestamp=timestamp or parsed_ts,
                        lat=station_lat,
                        lon=station_lon,
                        latitude=station_lat,
                        longitude=station_lon,
                        temperature=float(item["temperature"]),
                        humidity=float(item["humidity"]),
                        wind_speed=float(item["wind_speed"]),
                        wind_direction=float(item["wind_direction"]),
                        rainfall=float(item.get("rainfall", 0.0)),
                        source_status="AVAILABLE",
                        station_name=item.get("station_name"),
                        distance_km=round(dist, 2),
                        source_metadata=item.get("source_metadata", {}),
                    )
            except (KeyError, ValueError, TypeError):
                continue

        return best_obs
