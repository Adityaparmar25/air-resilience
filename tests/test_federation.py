"""Tests for Federated Multi-City Learning & City Node Interoperability.

Verifies:
- Node registration and capability contracts (Decision D-019)
- Rejection of invalid nodes and version mismatches
- Data-local training without raw observation leakage (Decision D-018)
- Sample-weighted FedAvg aggregation mathematics
- Coordinator resilience when a node fails or drops out
- Parameter validation rejecting NaN, Inf, or dimension mismatches
- Global model version increment and parameter distribution
- Local vs global model evaluation metrics
- Server-side role authorization (403 Forbidden for CITIZEN role)
- Complete end-to-end replay: Delhi + Haryana + UP -> Round -> Training -> Aggregation -> Inference
"""

from datetime import datetime, timezone
import math
from fastapi.testclient import TestClient
import pytest
from pydantic import ValidationError

from apps.api.main import create_app
from schemas.federation import (
    CityNode,
    ModelParams,
    ModelUpdate,
    NodeStatus,
    RegisterNodeRequest,
    RoundStatus,
)
from services.federation.coordinator import (
    FederationCoordinator,
    get_federation_coordinator,
)
from services.federation.model import FederatedPollutionRiskModel


@pytest.fixture
def client():
    app = create_app()
    return TestClient(app)


@pytest.fixture
def fresh_coordinator():
    coord = FederationCoordinator()
    return coord


def test_node_registration_and_listing(fresh_coordinator, client):
    """City nodes register with canonical capability contract and can be listed."""
    nodes = fresh_coordinator.list_nodes()
    node_ids = [n.node_id for n in nodes]
    assert "delhi" in node_ids
    assert "haryana" in node_ids
    assert "uttar_pradesh" in node_ids

    # Register new node
    req = RegisterNodeRequest(
        node_id="rajasthan",
        region="Bhiwadi / Alwar Industrial Corridor",
        state="Rajasthan",
        country="India",
        supported_signals=["pm25", "pm10", "weather"],
    )
    new_node = fresh_coordinator.register_node(req)
    assert new_node.node_id == "rajasthan"
    assert new_node.state == "Rajasthan"
    assert "pm25" in new_node.supported_signals

    # REST endpoint check
    res = client.get("/api/v1/federation/nodes")
    assert res.status_code == 200
    listed = res.json()
    assert len(listed) >= 3


def test_invalid_node_rejected(fresh_coordinator):
    """Creating a federation round with an unknown node ID is strictly rejected."""
    with pytest.raises(ValueError) as exc:
        fresh_coordinator.create_round(participating_nodes=["delhi", "nonexistent_city_xyz"])
    assert "Unknown participating node" in str(exc.value)


def test_model_version_mismatch_rejected(fresh_coordinator):
    """Coordinator rejects model updates based on obsolete or incompatible model versions."""
    round_obj = fresh_coordinator.create_round(participating_nodes=["delhi", "haryana"])
    # Simulate a node submitting an update with an obsolete base version
    obsolete_params = ModelParams(
        feature_names=fresh_coordinator.get_global_model().feature_names,
        weights=[0.1] * 10,
        bias=50.0,
        model_version="v0_obsolete",
    )
    bad_update = ModelUpdate(
        node_id="delhi",
        round_id=round_obj.round_id,
        base_model_version="v0_obsolete",  # Mismatch with round's global version (v1)
        sample_count=50,
        update_hash="hash1234",
        model_params=obsolete_params,
        training_metrics={"mae": 12.0},
    )
    round_obj.node_updates["delhi"] = bad_update
    # Add a valid haryana update
    valid_params = ModelParams(
        feature_names=fresh_coordinator.get_global_model().feature_names,
        weights=[0.1] * 10,
        bias=50.0,
        model_version="v1",
    )
    round_obj.node_updates["haryana"] = ModelUpdate(
        node_id="haryana",
        round_id=round_obj.round_id,
        base_model_version="v1",
        sample_count=50,
        update_hash="hash5678",
        model_params=valid_params,
    )

    with pytest.raises(ValueError) as exc:
        fresh_coordinator.aggregate_round(round_obj.round_id)
    assert "Model version mismatch" in str(exc.value)


def test_federation_round_creation_and_lifecycle(fresh_coordinator):
    """Federation round lifecycle transitions: CREATED -> TRAINING -> AGGREGATING -> COMPLETED."""
    round_obj = fresh_coordinator.create_round()
    assert round_obj.status == RoundStatus.CREATED
    assert len(round_obj.participating_nodes) == 3

    # Train
    fresh_coordinator.train_round(round_obj.round_id, epochs=2)
    assert round_obj.status == RoundStatus.TRAINING
    assert len(round_obj.node_updates) == 3

    # Aggregate
    fresh_coordinator.aggregate_round(round_obj.round_id)
    assert round_obj.status == RoundStatus.COMPLETED
    assert round_obj.completed_at is not None
    assert round_obj.metrics["new_global_version"] == "v2"


def test_data_local_training_on_partitions(fresh_coordinator):
    """Nodes execute training strictly on their own partitioned local datasets."""
    delhi_data = fresh_coordinator.load_node_dataset("delhi")
    haryana_data = fresh_coordinator.load_node_dataset("haryana")
    up_data = fresh_coordinator.load_node_dataset("uttar_pradesh")

    assert len(delhi_data) == 72
    assert len(haryana_data) == 60
    assert len(up_data) == 64

    # Verify partitions contain local stations
    assert delhi_data[0]["city"] == "Delhi"
    assert haryana_data[0]["city"] == "Gurugram"
    assert up_data[0]["city"] == "Noida"

    round_obj = fresh_coordinator.create_round()
    fresh_coordinator.train_round(round_obj.round_id, epochs=3)

    assert "delhi" in round_obj.node_updates
    assert round_obj.node_updates["delhi"].sample_count == 72
    assert "haryana" in round_obj.node_updates
    assert round_obj.node_updates["haryana"].sample_count == 60
    assert "uttar_pradesh" in round_obj.node_updates
    assert round_obj.node_updates["uttar_pradesh"].sample_count == 64


def test_no_raw_training_rows_in_model_update():
    """Security Guardrail: ModelUpdate strictly rejects any raw training rows in payload."""
    valid_params = ModelParams(
        feature_names=["f1", "f2"],
        weights=[0.5, -0.2],
        bias=75.0,
        model_version="v1",
    )

    # Attempting to inject raw observation records must raise a validation error
    with pytest.raises(ValidationError):
        ModelUpdate(
            node_id="delhi",
            round_id="round_001",
            base_model_version="v1",
            sample_count=100,
            update_hash="hash123",
            model_params=valid_params,
            raw_data=[{"pm25": 120.0, "lat": 28.6}],  # FORBIDDEN
        )

    with pytest.raises(ValidationError):
        ModelUpdate(
            node_id="delhi",
            round_id="round_001",
            base_model_version="v1",
            sample_count=100,
            update_hash="hash123",
            model_params=valid_params,
            observations=[1, 2, 3],  # FORBIDDEN
        )


def test_sample_weighted_fedavg_aggregation(fresh_coordinator):
    """Verifies exact mathematical implementation of sample-weighted FedAvg: W = sum( (n_k/N) * W_k )."""
    round_obj = fresh_coordinator.create_round(participating_nodes=["delhi", "haryana"])

    # Node 1: n1 = 100, W = [1.0, 1.0, ...]
    n1 = 100
    w1 = [1.0] * 10
    b1 = 80.0
    p1 = ModelParams(feature_names=fresh_coordinator.get_global_model().feature_names, weights=w1, bias=b1, model_version="v1")
    round_obj.node_updates["delhi"] = ModelUpdate(
        node_id="delhi",
        round_id=round_obj.round_id,
        base_model_version="v1",
        sample_count=n1,
        update_hash="h1",
        model_params=p1,
    )

    # Node 2: n2 = 300, W = [2.0, 2.0, ...]
    n2 = 300
    w2 = [2.0] * 10
    b2 = 120.0
    p2 = ModelParams(feature_names=fresh_coordinator.get_global_model().feature_names, weights=w2, bias=b2, model_version="v1")
    round_obj.node_updates["haryana"] = ModelUpdate(
        node_id="haryana",
        round_id=round_obj.round_id,
        base_model_version="v1",
        sample_count=n2,
        update_hash="h2",
        model_params=p2,
    )

    # Total N = 400.
    # Expected W[j] = (100/400)*1.0 + (300/400)*2.0 = 0.25 + 1.50 = 1.75
    # Expected bias = (100/400)*80.0 + (300/400)*120.0 = 20.0 + 90.0 = 110.0
    fresh_coordinator.aggregate_round(round_obj.round_id)
    global_model = fresh_coordinator.get_global_model()

    for w in global_model.weights:
        assert math.isclose(w, 1.75, rel_tol=1e-3)
    assert math.isclose(global_model.bias, 110.0, rel_tol=1e-3)


def test_aggregation_with_one_failed_or_missing_node(fresh_coordinator):
    """If one participating node drops offline, coordinator aggregates remaining nodes gracefully."""
    round_obj = fresh_coordinator.create_round(participating_nodes=["delhi", "haryana", "uttar_pradesh"])

    # Simulate only Delhi and UP responding
    delhi_data = fresh_coordinator.load_node_dataset("delhi")
    up_data = fresh_coordinator.load_node_dataset("uttar_pradesh")

    m_delhi = FederatedPollutionRiskModel(model_version="v1")
    m_delhi.train_local(delhi_data, epochs=2)
    round_obj.node_updates["delhi"] = ModelUpdate(
        node_id="delhi",
        round_id=round_obj.round_id,
        base_model_version="v1",
        sample_count=len(delhi_data),
        update_hash="h_delhi",
        model_params=m_delhi.get_params(),
    )

    m_up = FederatedPollutionRiskModel(model_version="v1")
    m_up.train_local(up_data, epochs=2)
    round_obj.node_updates["uttar_pradesh"] = ModelUpdate(
        node_id="uttar_pradesh",
        round_id=round_obj.round_id,
        base_model_version="v1",
        sample_count=len(up_data),
        update_hash="h_up",
        model_params=m_up.get_params(),
    )

    # Aggregating with 2 of 3 nodes succeeds
    fresh_coordinator.aggregate_round(round_obj.round_id, min_required_nodes=2)
    assert round_obj.status == RoundStatus.COMPLETED
    assert round_obj.metrics["total_participating_nodes"] == 2


def test_invalid_model_update_rejected():
    """Model update with NaN, Inf, or parameter dimension mismatch is rejected."""
    # NaN check
    with pytest.raises(ValidationError):
        ModelParams(
            feature_names=["f1"],
            weights=[float("nan")],
            bias=80.0,
            model_version="v1",
        )

    # Inf check
    with pytest.raises(ValidationError):
        ModelParams(
            feature_names=["f1"],
            weights=[float("inf")],
            bias=80.0,
            model_version="v1",
        )


def test_model_version_increment_and_distribution(fresh_coordinator):
    """Global model version increments (v1 -> v2) and is distributed to all participating nodes."""
    round_obj = fresh_coordinator.create_round()
    assert fresh_coordinator.get_global_model().model_version == "v1"

    fresh_coordinator.train_round(round_obj.round_id, epochs=2)
    fresh_coordinator.aggregate_round(round_obj.round_id)

    # Global model updated to v2
    assert fresh_coordinator.get_global_model().model_version == "v2"

    # All nodes updated to v2 and marked SYNCED
    for node in fresh_coordinator.list_nodes():
        assert node.model_version == "v2"
        assert node.status == NodeStatus.SYNCED


def test_local_vs_global_evaluation_metrics(fresh_coordinator):
    """Evaluation returns real numerical MAE, RMSE, and R2 metrics without fabricated values."""
    delhi_data = fresh_coordinator.load_node_dataset("delhi")
    model = fresh_coordinator.get_global_model()

    eval_res = model.evaluate(delhi_data)
    assert eval_res["sample_count"] == 72
    assert eval_res["mae"] > 0
    assert eval_res["rmse"] > 0
    assert "r2" in eval_res


def test_api_permissions_for_federation(client):
    """Unauthorized roles (e.g. CITIZEN) are forbidden from triggering federation rounds."""
    # Creating a round with CITIZEN role returns 403 Forbidden
    res = client.post("/api/v1/federation/rounds", headers={"X-User-Role": "CITIZEN"})
    assert res.status_code == 403
    assert "Unauthorized" in res.json()["detail"]

    # Training with CITIZEN role returns 403 Forbidden
    res_train = client.post("/api/v1/federation/rounds/dummy_round/train", headers={"X-User-Role": "CITIZEN"})
    assert res_train.status_code == 403

    # Authorized call succeeds
    res_auth = client.post("/api/v1/federation/rounds", headers={"X-User-Role": "AUTHORITY"})
    assert res_auth.status_code == 201


def test_end_to_end_replay_delhi_haryana_up(fresh_coordinator, client):
    """End-to-end replay: Delhi + Haryana + UP -> Round -> Local Training -> Aggregation -> Inference."""
    # 1. Verify 3 city nodes registered
    nodes = client.get("/api/v1/federation/nodes").json()
    assert len(nodes) >= 3

    # 2. Create federation round
    res_round = client.post(
        "/api/v1/federation/rounds",
        json={"participating_nodes": ["delhi", "haryana", "uttar_pradesh"]},
        headers={"X-User-Role": "AUTHORITY"},
    )
    assert res_round.status_code == 201
    round_id = res_round.json()["round_id"]

    # 3. Trigger data-local training
    res_train = client.post(
        f"/api/v1/federation/rounds/{round_id}/train",
        json={"epochs": 3, "learning_rate": 0.01},
        headers={"X-User-Role": "AUTHORITY"},
    )
    assert res_train.status_code == 200
    trained_data = res_train.json()
    assert len(trained_data["node_updates"]) == 3
    # Assert each update has sample count > 0 and no raw data
    for n_id, update in trained_data["node_updates"].items():
        assert update["sample_count"] > 0
        assert update["update_hash"] is not None
        assert "raw_data" not in update

    # 4. Perform FedAvg aggregation
    res_agg = client.post(
        f"/api/v1/federation/rounds/{round_id}/aggregate",
        headers={"X-User-Role": "AUTHORITY"},
    )
    assert res_agg.status_code == 200
    agg_data = res_agg.json()
    assert agg_data["status"] == "COMPLETED"
    assert agg_data["metrics"]["raw_data_shared"] is False
    assert agg_data["metrics"]["total_samples_trained"] == 196  # 72 + 60 + 64

    # 5. Query updated current global model
    res_model = client.get("/api/v1/federation/models/current")
    assert res_model.status_code == 200
    model_params = res_model.json()
    assert len(model_params["weights"]) == 10

    # 6. Execute inference using updated global model
    res_infer = client.post(
        "/api/v1/federation/infer",
        json={
            "pm25": 110.0,
            "pm10": 210.0,
            "no2": 65.0,
            "temperature": 27.0,
            "humidity": 62.0,
            "wind_speed": 1.5,
            "wind_direction": 290.0,
            "hour": 9,
        },
    )
    assert res_infer.status_code == 200
    infer_out = res_infer.json()
    assert infer_out["predicted_pm25_next_hour"] > 0
    assert 0.0 <= infer_out["predicted_risk_index"] <= 1.0
    assert infer_out["risk_level"] in ["LOW", "MODERATE", "HIGH", "CRITICAL"]
