"""CPCB (Central Pollution Control Board) Ingestion Adapter.

Handles fetching, structural validation, and field translation from real-world CPCB
data formats into canonical MonitoringObservation schema.
Preserves raw payload provenance and labels fixture vs live data.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

from schemas.canonical import MonitoringObservation


class CPCBAdapter:
    """Ingestion adapter for CPCB monitoring station data."""

    # Known station coordinate lookup table for Indian NCR / DMIC stations
    # Used when CPCB source payload provides station names/IDs without embedded lat/lon
    STATION_REGISTRY: Dict[str, Dict[str, Any]] = {
        "DL001": {
            "name": "Anand Vihar, Delhi",
            "lat": 28.6508,
            "lon": 77.3152,
            "city": "Delhi",
            "state": "Delhi",
        },
        "DL002": {
            "name": "R.K. Puram, Delhi",
            "lat": 28.5632,
            "lon": 77.1869,
            "city": "Delhi",
            "state": "Delhi",
        },
        "UP001": {
            "name": "Sector 62, Noida",
            "lat": 28.6245,
            "lon": 77.3639,
            "city": "Noida",
            "state": "Uttar Pradesh",
        },
        "HR001": {
            "name": "Vikas Sadan, Gurugram",
            "lat": 28.4595,
            "lon": 77.0266,
            "city": "Gurugram",
            "state": "Haryana",
        },
        "HR002": {
            "name": "IMT Manesar",
            "lat": 28.3630,
            "lon": 76.9280,
            "city": "Manesar",
            "state": "Haryana",
        },
        "RJ001": {
            "name": "RIICO Ind. Area, Bhiwadi",
            "lat": 28.2100,
            "lon": 76.8600,
            "city": "Bhiwadi",
            "state": "Rajasthan",
        },
    }

    # Common CPCB column variations
    STATION_ID_KEYS = ["station_id", "StationId", "stationId", "id", "site_id"]
    STATION_NAME_KEYS = ["station_name", "StationName", "station", "site_name", "Station Name"]
    TIMESTAMP_KEYS = ["timestamp", "Date", "date", "last_update", "From Date", "To Date", "datetime"]
    CITY_KEYS = ["city", "City"]
    STATE_KEYS = ["state", "State"]
    LAT_KEYS = ["lat", "latitude", "Latitude"]
    LON_KEYS = ["lon", "lng", "longitude", "Longitude"]

    POLLUTANT_KEY_MAP = {
        "pm25": ["pm25", "pm2_5", "PM2.5", "PM25", "PM2.5 (ug/m3)", "pm2.5", "PM 2.5"],
        "pm10": ["pm10", "PM10", "PM10 (ug/m3)", "PM 10"],
        "no2": ["no2", "NO2", "NO2 (ug/m3)", "Nitrogen Dioxide"],
        "so2": ["so2", "SO2", "SO2 (ug/m3)", "Sulphur Dioxide"],
        "co": ["co", "CO", "CO (mg/m3)", "Carbon Monoxide"],
        "o3": ["o3", "O3", "Ozone", "Ozone (ug/m3)", "OZONE"],
    }

    def __init__(self, default_fixture_path: Optional[str] = None):
        self.default_fixture_path = default_fixture_path

    def validate(self, raw_record: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate that raw record has minimum required identification fields."""
        if not isinstance(raw_record, dict):
            return False, "Raw record must be a dictionary"

        station_id = self._extract_first_match(raw_record, self.STATION_ID_KEYS)
        station_name = self._extract_first_match(raw_record, self.STATION_NAME_KEYS)
        if not station_id and not station_name:
            return False, "Missing station identifier (station_id or station_name)"

        ts_val = self._extract_first_match(raw_record, self.TIMESTAMP_KEYS)
        if ts_val is None or str(ts_val).strip() == "":
            return False, "Missing timestamp field"

        return True, None

    def normalize(
        self,
        raw_record: Dict[str, Any],
        is_fixture: bool = False,
    ) -> Tuple[MonitoringObservation, Dict[str, Any]]:
        """Translate CPCB raw record into canonical MonitoringObservation.

        Preserves source metadata and guarantees missing values remain None.
        """
        is_valid, error_msg = self.validate(raw_record)
        if not is_valid:
            raise ValueError(f"Invalid CPCB raw record: {error_msg}")

        # Extract station identity
        raw_station_id = self._extract_first_match(raw_record, self.STATION_ID_KEYS)
        raw_station_name = self._extract_first_match(raw_record, self.STATION_NAME_KEYS)

        station_id = str(raw_station_id or raw_station_name).strip()

        # Check registry fallback if lat/lon/city/state not in payload
        registry_meta = self.STATION_REGISTRY.get(station_id, {})
        if not registry_meta and raw_station_name:
            # Try lookup by name
            for reg_id, reg_info in self.STATION_REGISTRY.items():
                if reg_info["name"].lower() in str(raw_station_name).lower():
                    registry_meta = reg_info
                    break

        station_name = str(raw_station_name or registry_meta.get("name") or station_id).strip()

        lat = self._parse_float(
            self._extract_first_match(raw_record, self.LAT_KEYS)
            or registry_meta.get("lat")
        )
        lon = self._parse_float(
            self._extract_first_match(raw_record, self.LON_KEYS)
            or registry_meta.get("lon")
        )
        city = (
            self._extract_first_match(raw_record, self.CITY_KEYS)
            or registry_meta.get("city")
            or "Unknown City"
        )
        state = (
            self._extract_first_match(raw_record, self.STATE_KEYS)
            or registry_meta.get("state")
            or "Unknown State"
        )

        if lat is None or lon is None:
            raise ValueError(
                f"Missing coordinates for station {station_id} ({station_name}). "
                "Coordinates must be in payload or registered in STATION_REGISTRY."
            )

        # Parse timestamp
        raw_ts = self._extract_first_match(raw_record, self.TIMESTAMP_KEYS)
        timestamp = self._parse_timestamp(raw_ts)

        # Extract pollutants (missing remains None per D-007)
        pollutant_values: Dict[str, Optional[float]] = {}
        for canonical_name, aliases in self.POLLUTANT_KEY_MAP.items():
            raw_val = self._extract_first_match(raw_record, aliases)
            pollutant_values[canonical_name] = self._parse_float(raw_val)

        observation = MonitoringObservation(
            station_id=station_id,
            station_name=station_name,
            timestamp=timestamp,
            lat=float(lat),
            lon=float(lon),
            city=str(city).strip(),
            state=str(state).strip(),
            pm25=pollutant_values["pm25"],
            pm10=pollutant_values["pm10"],
            no2=pollutant_values["no2"],
            so2=pollutant_values["so2"],
            co=pollutant_values["co"],
            o3=pollutant_values["o3"],
        )

        metadata = {
            "data_source": "fixture" if is_fixture else "cpcb_live",
            "is_fixture": is_fixture,
            "raw_payload": raw_record,
            "ingested_at": datetime.now(timezone.utc).isoformat(),
        }

        return observation, metadata

    def fetch(
        self,
        station_id: Optional[str] = None,
        source_path: Optional[Union[str, Path]] = None,
        is_fixture: bool = True,
    ) -> List[Dict[str, Any]]:
        """Fetch raw records from local fixture file or configured source."""
        target_path = source_path or self.default_fixture_path
        if not target_path:
            raise ValueError("No source path or fixture path specified for CPCB fetch.")

        path = Path(target_path)
        if not path.exists():
            raise FileNotFoundError(f"CPCB data source file not found: {path}")

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        records: List[Dict[str, Any]] = []
        if isinstance(data, list):
            records = data
        elif isinstance(data, dict):
            if "records" in data and isinstance(data["records"], list):
                records = data["records"]
            elif "observations" in data and isinstance(data["observations"], list):
                records = data["observations"]
            else:
                records = [data]

        if station_id:
            records = [
                r for r in records
                if str(self._extract_first_match(r, self.STATION_ID_KEYS) or "").lower()
                == station_id.lower()
            ]

        return records

    def fetch_station_observations(
        self,
        station_id: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        fixture_path: Optional[str] = None,
    ) -> List[MonitoringObservation]:
        """Fetch and normalize station observations from fixture or source."""
        if not fixture_path:
            fixtures_dir = Path(__file__).resolve().parent.parent.parent / "data" / "fixtures"
            fixture_candidates = [
                fixtures_dir / f"{station_id.lower()}_series.json",
                fixtures_dir / "normal_series.json",
                fixtures_dir / "forecast_input.json",
            ]
            for candidate in fixture_candidates:
                if candidate.exists():
                    fixture_path = str(candidate)
                    break

        if not fixture_path:
            return []

        raw_records = self.fetch(source_path=fixture_path, station_id=station_id)
        if not raw_records:
            # Fall back to all records in the fixture if station filter returned none
            raw_records = self.fetch(source_path=fixture_path)

        observations: List[MonitoringObservation] = []
        for raw in raw_records:
            try:
                obs, _ = self.normalize(raw, is_fixture=True)
                observations.append(obs)
            except Exception:
                continue

        return observations

    @staticmethod
    def _extract_first_match(record: Dict[str, Any], candidates: List[str]) -> Any:
        """Return the value of the first key from candidates found in record."""
        for key in candidates:
            if key in record and record[key] is not None:
                return record[key]
        return None

    @staticmethod
    def _parse_float(val: Any) -> Optional[float]:
        """Safely parse float value; NA/empty strings converted to None (never 0.0)."""
        if val is None:
            return None
        if isinstance(val, (int, float)):
            return float(val)
        val_str = str(val).strip()
        if val_str.lower() in {"", "null", "none", "na", "n/a", "-", "nan"}:
            return None
        try:
            return float(val_str)
        except ValueError:
            return None

    @staticmethod
    def _parse_timestamp(val: Any) -> datetime:
        """Parse various timestamp string formats into UTC-aware datetime."""
        if isinstance(val, datetime):
            if val.tzinfo is None:
                return val.replace(tzinfo=timezone.utc)
            return val.astimezone(timezone.utc)

        if isinstance(val, (int, float)):
            # Epoch seconds or milliseconds
            if val > 1e11:
                val = val / 1000.0
            return datetime.fromtimestamp(val, tz=timezone.utc)

        val_str = str(val).strip()
        # Try ISO format
        try:
            dt = datetime.fromisoformat(val_str)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            pass

        # Try standard CPCB formats
        common_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%d-%m-%Y %H:%M:%S",
            "%d-%m-%Y %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
            "%Y/%m/%d %H:%M:%S",
        ]
        for fmt in common_formats:
            try:
                dt = datetime.strptime(val_str, fmt)
                return dt.replace(tzinfo=timezone.utc)
            except ValueError:
                continue

        raise ValueError(f"Unable to parse timestamp format: {val_str}")
