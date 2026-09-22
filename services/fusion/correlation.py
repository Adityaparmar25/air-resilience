"""Spatio-Temporal Correlation and Event Deduplication Service.

Computes geographical distances, temporal alignment, and spatial clustering
to prevent duplicate event creation when multiple citizen reports describe the same incident.
"""

from datetime import datetime, timezone
import math
from typing import Any, Dict, List, Optional, Tuple

from schemas.event import PollutionEvent
from services.ingestion.cpcb_adapter import CPCBAdapter


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculate the great-circle distance between two coordinate pairs in kilometers."""
    radius_earth_km = 6371.0

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return radius_earth_km * c


def generate_cell_id(lat: float, lon: float, grid_size: float = 0.05) -> str:
    """Generate a coarsened spatial grid cell identifier (approx 5km resolution)."""
    cell_lat = round(lat / grid_size) * grid_size
    cell_lon = round(lon / grid_size) * grid_size
    return f"cell_{cell_lat:.2f}_{cell_lon:.2f}"


class SpatioTemporalCorrelationService:
    """Service to cluster signals and associate incoming reports with existing events."""

    DEFAULT_SPATIAL_RADIUS_KM = 5.0
    DEFAULT_TEMPORAL_WINDOW_HOURS = 3.0

    @classmethod
    def find_nearby_stations(
        cls,
        lat: float,
        lon: float,
        max_distance_km: float = 12.0,
    ) -> List[Tuple[str, Dict[str, Any], float]]:
        """Find registered monitoring stations within search radius, sorted by distance."""
        nearby = []
        for station_id, info in CPCBAdapter.STATION_REGISTRY.items():
            st_lat = info.get("lat")
            st_lon = info.get("lon")
            if st_lat is not None and st_lon is not None:
                dist = haversine_distance_km(lat, lon, st_lat, st_lon)
                if dist <= max_distance_km:
                    nearby.append((station_id, info, round(dist, 2)))

        nearby.sort(key=lambda x: x[2])
        return nearby

    @classmethod
    def find_matching_event(
        cls,
        lat: float,
        lon: float,
        timestamp: datetime,
        active_events: List[PollutionEvent],
        spatial_radius_km: float = DEFAULT_SPATIAL_RADIUS_KM,
        temporal_window_hours: float = DEFAULT_TEMPORAL_WINDOW_HOURS,
    ) -> Optional[Tuple[PollutionEvent, float, float]]:
        """Identify if an existing active event matches the location and time window.

        Returns (matched_event, distance_km, time_diff_hours) or None if no match.
        """
        for event in active_events:
            # Check spatial distance
            dist_km = haversine_distance_km(lat, lon, event.location.lat, event.location.lng)
            if dist_km <= spatial_radius_km:
                # Check temporal difference
                time_diff_hours = abs((timestamp - event.timestamp).total_seconds()) / 3600.0
                if time_diff_hours <= temporal_window_hours:
                    return event, round(dist_km, 2), round(time_diff_hours, 2)

        return None
