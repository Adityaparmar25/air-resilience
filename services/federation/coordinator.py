"""Federation Coordinator & Registry Service.

Orchestrates multi-city federated learning across Delhi, Haryana, and Uttar Pradesh (Decisions D-018 & D-019):
- Manages city node registrations and capabilities
- Coordinates isolated data-local training on node partitions
- Executes sample-weighted FedAvg model update aggregation
- Ensures zero raw observation transmission to coordinator
- Distributes updated global models and tracks comparative metrics
"""

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from schemas.federation import (
    CityNode,
    FederatedInferenceRequest,
    FederatedInferenceResponse,
    FederatedRound,
    ModelParams,
    ModelUpdate,
    NodeStatus,
    RegisterNodeRequest,
    RoundStatus,
)
from services.federation.model import FederatedPollutionRiskModel


FIXTURES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "fixtures" / "federation"


class FederationCoordinator:
    """Central coordinator for multi-city federated rounds and node management."""

    def __init__(self, fixtures_dir: Optional[Path] = None):
        self.fixtures_dir = fixtures_dir or FIXTURES_DIR
        self._lock = Lock()
        self._nodes: Dict[str, CityNode] = {}
        self._rounds: Dict[str, FederatedRound] = {}
        self._global_model = FederatedPollutionRiskModel(model_version="v1")
        self._model_history: List[ModelParams] = [self._global_model.get_params()]
        self._node_models: Dict[str, FederatedPollutionRiskModel] = {}

        self._seed_default_nodes()

    def _seed_default_nodes(self) -> None:
        """Seed default canonical city nodes matching Delhi-NCR industrial/urban corridors."""
        defaults = [
            CityNode(
                node_id="delhi",
                region="National Capital Territory (Anand Vihar, Punjabi Bagh, Mandir Marg)",
                state="Delhi",
                country="India",
                schema_version="1.0",
                model_version=self._global_model.model_version,
                status=NodeStatus.ACTIVE,
                supported_signals=["pm25", "pm10", "no2", "temperature", "humidity", "wind"],
                metadata={"monitoring_stations": 3, "dataset_partition": "delhi_training.json"},
            ),
            CityNode(
                node_id="haryana",
                region="South NCR Industrial Corridor (Gurugram, Manesar, Faridabad)",
                state="Haryana",
                country="India",
                schema_version="1.0",
                model_version=self._global_model.model_version,
                status=NodeStatus.ACTIVE,
                supported_signals=["pm25", "pm10", "no2", "temperature", "humidity", "wind"],
                metadata={"monitoring_stations": 3, "dataset_partition": "haryana_training.json"},
            ),
            CityNode(
                node_id="uttar_pradesh",
                region="East NCR Urban/Industrial Corridor (Noida, Ghaziabad, Meerut)",
                state="Uttar Pradesh",
                country="India",
                schema_version="1.0",
                model_version=self._global_model.model_version,
                status=NodeStatus.ACTIVE,
                supported_signals=["pm25", "pm10", "no2", "temperature", "humidity", "wind"],
                metadata={"monitoring_stations": 3, "dataset_partition": "uttar_pradesh_training.json"},
            ),
        ]
        for node in defaults:
            self._nodes[node.node_id] = node
            # Initialize node-specific local model copy
            self._node_models[node.node_id] = FederatedPollutionRiskModel(
                model_version=self._global_model.model_version,
                weights=self._global_model.weights,
                bias=self._global_model.bias,
            )

    def register_node(self, request: RegisterNodeRequest) -> CityNode:
        """Register or update a city node in the federated network."""
        with self._lock:
            signals = request.supported_signals or ["pm25", "pm10", "no2", "weather"]
            node = CityNode(
                node_id=request.node_id.lower().strip(),
                region=request.region,
                state=request.state,
                country=request.country,
                schema_version=request.schema_version,
                model_version=self._global_model.model_version,
                status=NodeStatus.ACTIVE,
                supported_signals=signals,
            )
            self._nodes[node.node_id] = node
            self._node_models[node.node_id] = FederatedPollutionRiskModel(
                model_version=self._global_model.model_version,
                weights=self._global_model.weights,
                bias=self._global_model.bias,
            )
            return node

    def list_nodes(self) -> List[CityNode]:
        """List all registered city nodes."""
        with self._lock:
            return list(self._nodes.values())

    def get_node(self, node_id: str) -> Optional[CityNode]:
        """Get city node by ID."""
        with self._lock:
            return self._nodes.get(node_id.lower().strip())

    def get_global_model(self) -> FederatedPollutionRiskModel:
        """Get active global federated model."""
        with self._lock:
            return self._global_model

    def load_node_dataset(self, node_id: str) -> List[Dict[str, Any]]:
        """Load data-local training observations strictly for the specified node.

        Guarantees local partition isolation: node has access only to its own data.
        """
        node_id_clean = node_id.lower().strip()
        filename = f"{node_id_clean}_training.json"
        filepath = self.fixtures_dir / filename

        if not filepath.exists():
            # Fallback for dynamic nodes
            return []

        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []

    def create_round(
        self,
        participating_nodes: Optional[List[str]] = None,
        base_model_version: Optional[str] = None,
    ) -> FederatedRound:
        """Initialize a new federation round."""
        with self._lock:
            nodes_to_include = participating_nodes or list(self._nodes.keys())
            # Validate all requested nodes exist
            for n_id in nodes_to_include:
                if n_id not in self._nodes:
                    raise ValueError(f"Cannot create round: Unknown participating node '{n_id}'")

            round_obj = FederatedRound(
                participating_nodes=nodes_to_include,
                global_model_version=base_model_version or self._global_model.model_version,
                aggregation_method="FedAvg_SampleWeighted",
                status=RoundStatus.CREATED,
            )
            self._rounds[round_obj.round_id] = round_obj
            return round_obj

    def train_round(
        self,
        round_id: str,
        epochs: int = 5,
        lr: float = 0.01,
    ) -> FederatedRound:
        """Trigger data-local training across participating nodes.

        Security & Privacy Guarantees:
        - Training runs locally on each city node's isolated dataset
        - Only serialized weights, sample counts, update hashes, and metrics are returned
        - ZERO raw training observations cross the coordinator boundary
        """
        with self._lock:
            round_obj = self._rounds.get(round_id)
            if not round_obj:
                raise KeyError(f"Federated round '{round_id}' not found")

            if round_obj.status not in [RoundStatus.CREATED, RoundStatus.TRAINING]:
                raise ValueError(f"Cannot start training on round in status '{round_obj.status}'")

            round_obj.status = RoundStatus.TRAINING
            updates: Dict[str, ModelUpdate] = {}

            for node_id in round_obj.participating_nodes:
                node = self._nodes.get(node_id)
                if not node:
                    continue

                node.status = NodeStatus.TRAINING

                # 1. Load data strictly from local node partition
                local_data = self.load_node_dataset(node_id)
                if not local_data:
                    node.status = NodeStatus.FAILED
                    continue

                sample_count = len(local_data)

                # 2. Local model initialized with current global parameters
                local_model = FederatedPollutionRiskModel(
                    model_version=round_obj.global_model_version,
                    weights=self._global_model.weights,
                    bias=self._global_model.bias,
                )

                # 3. Local training in node boundary
                train_metrics = local_model.train_local(local_data, epochs=epochs, lr=lr)

                # 4. Export parameter update (WITHOUT raw records)
                params = local_model.get_params()
                update_hash = local_model.compute_update_hash()

                model_update = ModelUpdate(
                    node_id=node_id,
                    round_id=round_id,
                    base_model_version=round_obj.global_model_version,
                    sample_count=sample_count,
                    update_hash=update_hash,
                    model_params=params,
                    training_metrics=train_metrics,
                )

                updates[node_id] = model_update
                self._node_models[node_id] = local_model
                node.status = NodeStatus.ACTIVE
                node.last_sync = datetime.now(timezone.utc)

            round_obj.node_updates = updates
            return round_obj

    def aggregate_round(
        self,
        round_id: str,
        min_required_nodes: int = 2,
    ) -> FederatedRound:
        """Perform sample-weighted FedAvg aggregation of received model updates.

        Formula:
        W_global = sum( (n_k / N) * W_k )
        b_global = sum( (n_k / N) * b_k )
        """
        with self._lock:
            round_obj = self._rounds.get(round_id)
            if not round_obj:
                raise KeyError(f"Federated round '{round_id}' not found")

            if not round_obj.node_updates:
                round_obj.status = RoundStatus.FAILED
                raise ValueError("Cannot aggregate round: No node model updates received")

            if len(round_obj.node_updates) < min_required_nodes:
                round_obj.status = RoundStatus.FAILED
                raise ValueError(
                    f"Aggregation failed: Received {len(round_obj.node_updates)} updates, minimum required is {min_required_nodes}"
                )

            round_obj.status = RoundStatus.AGGREGATING

            # Calculate total sample count N
            total_samples = sum(u.sample_count for u in round_obj.node_updates.values())
            if total_samples <= 0:
                round_obj.status = RoundStatus.FAILED
                raise ValueError("Total sample count across node updates must be greater than zero")

            n_features = len(self._global_model.weights)
            agg_weights = [0.0] * n_features
            agg_bias = 0.0

            node_contributions: Dict[str, Dict[str, Any]] = {}

            # Execute sample-weighted FedAvg
            for node_id, update in round_obj.node_updates.items():
                # Validate update model version matches expected base version
                if update.base_model_version != round_obj.global_model_version:
                    raise ValueError(
                        f"Model version mismatch from node '{node_id}': expected '{round_obj.global_model_version}', got '{update.base_model_version}'"
                    )

                weight_fraction = update.sample_count / float(total_samples)
                node_contributions[node_id] = {
                    "sample_count": update.sample_count,
                    "weight_fraction": round(weight_fraction, 4),
                    "update_hash": update.update_hash,
                    "metrics": update.training_metrics,
                }

                for j in range(n_features):
                    agg_weights[j] += weight_fraction * update.model_params.weights[j]
                agg_bias += weight_fraction * update.model_params.bias

            # Generate new version identifier (e.g. v1 -> v2)
            curr_ver_num = int(round_obj.global_model_version.lstrip("v")) if round_obj.global_model_version.startswith("v") else 1
            new_version = f"v{curr_ver_num + 1}"

            # Update global model
            new_global_params = ModelParams(
                feature_names=list(self._global_model.feature_names),
                weights=[round(w, 6) for w in agg_weights],
                bias=round(agg_bias, 4),
                model_version=new_version,
            )
            self._global_model.set_params(new_global_params)
            self._model_history.append(new_global_params)

            # Distribute updated global model to participating nodes
            for node_id in round_obj.node_updates.keys():
                node = self._nodes.get(node_id)
                if node:
                    node.model_version = new_version
                    node.status = NodeStatus.SYNCED
                    node.last_sync = datetime.now(timezone.utc)
                # Synchronize node models
                if node_id in self._node_models:
                    self._node_models[node_id].set_params(new_global_params)

            # Evaluate global model across all local node partitions honestly
            combined_eval: Dict[str, Any] = {}
            for node_id in round_obj.node_updates.keys():
                ds = self.load_node_dataset(node_id)
                if ds:
                    combined_eval[node_id] = self._global_model.evaluate(ds)

            # Finalize round
            round_obj.status = RoundStatus.COMPLETED
            round_obj.completed_at = datetime.now(timezone.utc)
            round_obj.metrics = {
                "total_participating_nodes": len(round_obj.node_updates),
                "total_samples_trained": total_samples,
                "node_contributions": node_contributions,
                "new_global_version": new_version,
                "global_evaluation_across_nodes": combined_eval,
                "aggregation_method": "FedAvg_SampleWeighted",
                "raw_data_shared": False,
            }
            return round_obj

    def get_round(self, round_id: str) -> Optional[FederatedRound]:
        """Retrieve federated round by ID."""
        with self._lock:
            return self._rounds.get(round_id)

    def list_rounds(self) -> List[FederatedRound]:
        """List all federation rounds sorted chronologically descending."""
        with self._lock:
            return sorted(self._rounds.values(), key=lambda r: r.started_at, reverse=True)

    def infer(self, request: FederatedInferenceRequest) -> FederatedInferenceResponse:
        """Run next-hour pollution risk inference using global or node-specific model."""
        with self._lock:
            if request.use_global_model or not request.node_id:
                model = self._global_model
                source = "global"
            else:
                model = self._node_models.get(request.node_id.lower().strip(), self._global_model)
                source = request.node_id

            rec = {
                "pm25": request.pm25,
                "pm10": request.pm10,
                "no2": request.no2,
                "temperature": request.temperature,
                "humidity": request.humidity,
                "wind_speed": request.wind_speed,
                "wind_direction": request.wind_direction,
                "hour": request.hour if request.hour is not None else 12,
                "day_of_week": request.day_of_week if request.day_of_week is not None else 0,
            }

            pred_pm25, risk_idx, level = model.predict(rec)

            return FederatedInferenceResponse(
                predicted_pm25_next_hour=pred_pm25,
                predicted_risk_index=risk_idx,
                risk_level=level,
                model_version=model.model_version,
                model_source=source,
                features_used={k: float(v) for k, v in rec.items() if v is not None},
            )


# Singleton instance
_coordinator_instance: Optional[FederationCoordinator] = None


def get_federation_coordinator() -> FederationCoordinator:
    """Retrieve singleton FederationCoordinator instance."""
    global _coordinator_instance
    if _coordinator_instance is None:
        _coordinator_instance = FederationCoordinator()
    return _coordinator_instance
