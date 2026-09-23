"""Federated Learning and Multi-City Interoperability Schemas.

Adheres strictly to Decisions D-018 and D-019:
- Data-local training with federated model-update aggregation
- Zero raw observation transmission to coordinator
- Transparent sample-weighted FedAvg aggregation
- City-agnostic node contracts
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid
from pydantic import BaseModel, Field, field_validator, model_validator


class NodeStatus(str, Enum):
    """Operational state of a federated city node."""

    ACTIVE = "ACTIVE"
    OFFLINE = "OFFLINE"
    TRAINING = "TRAINING"
    SYNCED = "SYNCED"
    FAILED = "FAILED"


class RoundStatus(str, Enum):
    """Lifecycle status of a federated training round."""

    CREATED = "CREATED"
    TRAINING = "TRAINING"
    AGGREGATING = "AGGREGATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class NodeCapability(BaseModel):
    """Canonical node interoperability contract (Decision D-019)."""

    node_id: str
    schema_version: str = "1.0"
    supported_signals: List[str] = Field(
        default_factory=lambda: ["pm25", "pm10", "no2", "weather"]
    )
    model_version: str = "v1"


class CityNode(BaseModel):
    """City Node representation in the federated network."""

    node_id: str = Field(..., description="Unique city/region identifier (e.g. 'delhi', 'haryana', 'uttar_pradesh')")
    region: str = Field(..., description="Geographic jurisdiction or corridor")
    state: str = Field(..., description="State or union territory")
    country: str = Field(default="India")
    schema_version: str = Field(default="1.0")
    model_version: str = Field(default="v1", description="Current deployed model version on this node")
    last_sync: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: NodeStatus = Field(default=NodeStatus.ACTIVE)
    supported_signals: List[str] = Field(
        default_factory=lambda: ["pm25", "pm10", "no2", "weather"]
    )
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ModelParams(BaseModel):
    """Serialized mathematical parameters of the federated pollution-risk model."""

    feature_names: List[str]
    weights: List[float]
    bias: float
    model_version: str = "v1"

    @field_validator("weights")
    @classmethod
    def validate_weights_finite(cls, v: List[float]) -> List[float]:
        import math
        for w in v:
            if math.isnan(w) or math.isinf(w):
                raise ValueError("Model weights must contain finite numerical values (no NaN or Inf)")
        return v


class ModelUpdate(BaseModel):
    """Federated model update submitted by a city node to coordinator.

    Strict Guardrail: Under no circumstances does this payload contain raw training rows.
    Only model parameters, sample counts, integrity hashes, and training metrics are permitted.
    """

    node_id: str
    round_id: str
    base_model_version: str
    sample_count: int = Field(..., ge=1, description="Number of local observations used for local training")
    update_hash: str = Field(..., description="SHA-256 parameter digest for integrity verification")
    model_params: ModelParams
    training_metrics: Dict[str, float] = Field(
        default_factory=dict,
        description="Local training metrics (loss, mae, rmse, r2)",
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @model_validator(mode="before")
    @classmethod
    def reject_raw_training_data(cls, values: Any) -> Any:
        if isinstance(values, dict):
            prohibited_keys = ["raw_data", "observations", "training_rows", "records", "samples", "raw_records"]
            for k in prohibited_keys:
                if k in values:
                    raise ValueError(
                        f"Violation of Federation Security Guardrail (D-018): Raw training data field '{k}' is forbidden in model update payload."
                    )
        return values


class FederatedRound(BaseModel):
    """Canonical representation of a federated training and aggregation round."""

    round_id: str = Field(default_factory=lambda: f"round_{uuid.uuid4().hex[:8]}")
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    participating_nodes: List[str]
    global_model_version: str = "v1"
    aggregation_method: str = "FedAvg_SampleWeighted"
    status: RoundStatus = Field(default=RoundStatus.CREATED)
    metrics: Dict[str, Any] = Field(default_factory=dict)
    node_updates: Dict[str, ModelUpdate] = Field(default_factory=dict)


# --- Request and Response DTOs ---

class RegisterNodeRequest(BaseModel):
    node_id: str = Field(..., min_length=2, max_length=50)
    region: str
    state: str
    country: str = "India"
    schema_version: str = "1.0"
    supported_signals: Optional[List[str]] = None


class CreateRoundRequest(BaseModel):
    participating_nodes: Optional[List[str]] = None
    base_model_version: Optional[str] = None


class TrainRoundRequest(BaseModel):
    epochs: int = Field(default=5, ge=1, le=50)
    learning_rate: float = Field(default=0.01, ge=0.0001, le=1.0)


class AggregateRoundRequest(BaseModel):
    min_required_nodes: int = Field(default=2, ge=1)


class FederatedInferenceRequest(BaseModel):
    node_id: Optional[str] = None
    use_global_model: bool = True
    pm25: float
    pm10: Optional[float] = None
    no2: Optional[float] = None
    temperature: Optional[float] = 25.0
    humidity: Optional[float] = 50.0
    wind_speed: Optional[float] = 2.0
    wind_direction: Optional[float] = 270.0
    hour: Optional[int] = None
    day_of_week: Optional[int] = None


class FederatedInferenceResponse(BaseModel):
    predicted_pm25_next_hour: float
    predicted_risk_index: float = Field(..., ge=0.0, le=1.0)
    risk_level: str
    model_version: str
    model_source: str  # "global" or specific node_id
    features_used: Dict[str, float]
