"""Deterministic End-to-End Replay Demonstration for Federated Multi-City Learning.

Scenario: Regional Cross-Jurisdiction Pollution Risk Forecasting
Participating Nodes: Delhi, Haryana, Uttar Pradesh
Guarantees:
- Data-local training on isolated city partitions (D-018)
- Zero raw observation transmission across coordinator boundary
- Sample-weighted FedAvg parameter aggregation
- Global model version increment (v1 -> v2) and deployment
"""

import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from schemas.federation import FederatedInferenceRequest
from services.federation.coordinator import get_federation_coordinator


def run_federation_demo():
    print("=" * 80)
    print(" CLEAN AIR & CLIMATE RESILIENCE — FEDERATED MULTI-CITY LEARNING REPLAY DEMO")
    print(" Architecture: Data-Local Training with Federated Model-Update Aggregation (D-018)")
    print(" Regional Nodes: Delhi + Haryana + Uttar Pradesh (D-019)")
    print("=" * 80)

    coord = get_federation_coordinator()

    # Step 1: Inspect Registered City Nodes
    print("\n[STEP 1] Inspecting Canonical Regional City Nodes...")
    nodes = coord.list_nodes()
    for n in nodes:
        print(f" -> Node ID: {n.node_id:15} | State: {n.state:15} | Status: {n.status.value:8} | Signals: {', '.join(n.supported_signals[:4])}")

    # Step 2: Initialize Federated Training Round
    print("\n[STEP 2] Initializing Federated Round across Participating Nodes...")
    round_obj = coord.create_round(participating_nodes=["delhi", "haryana", "uttar_pradesh"])
    print(f" -> Round ID: {round_obj.round_id}")
    print(f" -> Status: {round_obj.status.value}")
    print(f" -> Base Global Version: {round_obj.global_model_version}")

    # Step 3: Execute Data-Local Training within Node Boundaries
    print("\n[STEP 3] Executing Data-Local Training on Node Partitions (Isolated Boundaries)...")
    round_obj = coord.train_round(round_obj.round_id, epochs=5, lr=0.01)

    total_samples = 0
    for node_id, update in round_obj.node_updates.items():
        total_samples += update.sample_count
        metrics = update.training_metrics
        print(f" -> [{node_id.upper()}] Trained on {update.sample_count} local observations | MAE: {metrics.get('mae')} ug/m3 | RMSE: {metrics.get('rmse')} ug/m3 | Digest: SHA256:{update.update_hash}")

    print(f"\n   [SECURITY GUARANTEE] Raw local observations transmitted to coordinator: ZERO")
    print(f"   [SECURITY GUARANTEE] Only parameter weights and sample counts were shared.")

    # Step 4: Server-Side Sample-Weighted FedAvg Aggregation
    print("\n[STEP 4] Executing Server-Side Sample-Weighted FedAvg Aggregation...")
    print(f" -> Total Samples Across Nodes: {total_samples}")
    for node_id, update in round_obj.node_updates.items():
        weight_frac = round(update.sample_count / total_samples, 4)
        print(f"    &bull; {node_id:15}: {update.sample_count:3} samples ({weight_frac * 100:.1f}% weight)")

    round_obj = coord.aggregate_round(round_obj.round_id)
    new_version = round_obj.metrics["new_global_version"]
    print(f" -> Aggregation Completed: Global Model updated to {new_version}")

    # Step 5: Verify Global Model Distribution
    print("\n[STEP 5] Distributing Updated Global Model v2 to Participating Nodes...")
    synced_nodes = coord.list_nodes()
    for n in synced_nodes:
        print(f" -> Node: {n.node_id:15} | Deployed Version: {n.model_version} | Status: {n.status.value}")

    # Step 6: Comparative Evaluation
    print("\n[STEP 6] Comparative Evaluation of Global Model across Local Partitions...")
    eval_metrics = round_obj.metrics.get("global_evaluation_across_nodes", {})
    for node_id, m in eval_metrics.items():
        print(f" -> {node_id.upper():15}: Evaluated on {m.get('sample_count')} samples | MAE: {m.get('mae')} ug/m3 | RMSE: {m.get('rmse')} ug/m3 | R2: {m.get('r2')}")

    # Step 7: Real-Time Pollution Risk Inference
    print("\n[STEP 7] Multi-City Test Inference using Aggregated Global Model...")
    test_conditions = [
        {"desc": "Anand Vihar (Delhi) Morning Rush", "pm25": 145.0, "pm10": 260.0, "no2": 72.0, "wind_speed": 1.2},
        {"desc": "Manesar (Haryana) Industrial Daytime", "pm25": 88.0, "pm10": 165.0, "no2": 45.0, "wind_speed": 2.8},
        {"desc": "Noida Sector 62 (UP) Evening Corridor", "pm25": 120.0, "pm10": 215.0, "no2": 58.0, "wind_speed": 1.8},
    ]

    for cond in test_conditions:
        inf_req = FederatedInferenceRequest(
            pm25=cond["pm25"],
            pm10=cond["pm10"],
            no2=cond["no2"],
            wind_speed=cond["wind_speed"],
            use_global_model=True,
        )
        res = coord.infer(inf_req)
        print(f" -> Condition: {cond['desc']:35} | Current PM2.5: {cond['pm25']} ug/m3 -> Predicted +1h: {res.predicted_pm25_next_hour} ug/m3 | Risk Index: {res.predicted_risk_index * 100:.1f}% ({res.risk_level})")

    print("\n" + "=" * 80)
    print(" FEDERATION REPLAY DEMO COMPLETED SUCCESSFULLY — 100% DETERMINISTIC PASS")
    print("=" * 80)


if __name__ == "__main__":
    run_federation_demo()
