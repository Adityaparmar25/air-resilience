"""Federated Pollution Risk Model.

A lightweight, transparent linear regressor supporting data-local training,
gradient updates, and parameter serialization for FedAvg aggregation (Decision D-018).

Features:
- pm25 (standardized)
- pm10 (standardized)
- no2 (standardized)
- temperature (standardized)
- humidity (standardized)
- wind_speed (standardized)
- wind_dir_sin, wind_dir_cos
- hour_sin, hour_cos

Target:
- target_pm25_next_hour (ug/m3) -> mapped to next-hour pollution risk index (0.0 to 1.0)
"""

import hashlib
import json
import math
from typing import Any, Dict, List, Optional, Tuple
from schemas.federation import ModelParams


FEATURE_NAMES = [
    "pm25_norm",
    "pm10_norm",
    "no2_norm",
    "temp_norm",
    "humidity_norm",
    "wind_speed_norm",
    "wind_sin",
    "wind_cos",
    "hour_sin",
    "hour_cos",
]


def compute_risk_category(score: float) -> str:
    """Standardized risk level mapping across all services:
    0.0 <= score < 25.0: "LOW"
    25.0 <= score < 50.0: "MODERATE"
    50.0 <= score < 75.0: "HIGH"
    75.0 <= score <= 100.0: "CRITICAL"
    """
    # If passed as 0.0 to 1.0 ratio, convert to 0-100 percentage
    val = score * 100.0 if (0.0 < score <= 1.0) else score

    if val < 25.0:
        return "LOW"
    elif val < 50.0:
        return "MODERATE"
    elif val < 75.0:
        return "HIGH"
    else:
        return "CRITICAL"


class FederatedPollutionRiskModel:
    """Lightweight trainable model for local node training and server-side FedAvg."""

    def __init__(
        self,
        model_version: str = "v1",
        weights: Optional[List[float]] = None,
        bias: Optional[float] = None,
    ):
        self.model_version = model_version
        self.feature_names = list(FEATURE_NAMES)
        n_features = len(self.feature_names)

        if weights is not None:
            if len(weights) != n_features:
                raise ValueError(f"Expected {n_features} weights, got {len(weights)}")
            self.weights = [float(w) for w in weights]
        else:
            # Baseline domain-informed starting weights
            # PM2.5 auto-correlation is high, wind speed has negative coefficient (dispersion)
            self.weights = [
                0.65,   # pm25_norm
                0.15,   # pm10_norm
                0.10,   # no2_norm
                -0.05,  # temp_norm
                0.05,   # humidity_norm
                -0.12,  # wind_speed_norm (dispersion cooling)
                -0.02,  # wind_sin
                0.03,   # wind_cos
                0.08,   # hour_sin (diurnal cycle)
                0.06,   # hour_cos
            ]

        self.bias = float(bias) if bias is not None else 80.0

    def extract_features(self, record: Dict[str, Any]) -> List[float]:
        """Convert raw observation record into standardized numerical feature vector."""
        pm25 = float(record.get("pm25") or 80.0)
        pm10 = float(record.get("pm10") or pm25 * 1.8)
        no2 = float(record.get("no2") or 45.0)
        temp = float(record.get("temperature") or 25.0)
        humidity = float(record.get("humidity") or 55.0)
        wind_speed = float(record.get("wind_speed") or 2.0)
        wind_dir = float(record.get("wind_direction") or 270.0)
        hour = int(record.get("hour") if record.get("hour") is not None else 12)

        wind_rad = math.radians(wind_dir)
        hour_rad = 2.0 * math.pi * (hour / 24.0)

        # Standardization with reference means & stds
        return [
            (pm25 - 80.0) / 45.0,
            (pm10 - 160.0) / 85.0,
            (no2 - 50.0) / 25.0,
            (temp - 26.0) / 8.0,
            (humidity - 60.0) / 20.0,
            (wind_speed - 2.5) / 1.5,
            math.sin(wind_rad),
            math.cos(wind_rad),
            math.sin(hour_rad),
            math.cos(hour_rad),
        ]

    def predict_value(self, x: List[float]) -> float:
        """Linear dot-product prediction: y_pred = dot(W, x) * 45.0 + bias."""
        dot = sum(w * xi for w, xi in zip(self.weights, x))
        pred = dot * 45.0 + self.bias
        return round(max(5.0, pred), 2)

    def predict(self, record: Dict[str, Any]) -> Tuple[float, float, str]:
        """Generate prediction for a single observation record.

        Returns: (predicted_pm25_next_hour, risk_index, risk_level)
        """
        x = self.extract_features(record)
        pred_pm25 = self.predict_value(x)

        # Risk Index (0.0 to 1.0) scaled against severe threshold (250 ug/m3)
        risk_index = min(1.0, max(0.0, round(pred_pm25 / 250.0, 3)))
        risk_level = compute_risk_category(risk_index * 100.0)

        return pred_pm25, risk_index, risk_level

    def train_local(
        self,
        dataset: List[Dict[str, Any]],
        epochs: int = 5,
        lr: float = 0.05,
        l2_reg: float = 0.001,
    ) -> Dict[str, float]:
        """Perform data-local mini-batch gradient descent on node observations.

        Updates local weights and bias in place.
        Returns training metrics (loss, mae, rmse, r2).
        """
        if not dataset:
            raise ValueError("Local training dataset cannot be empty")

        X: List[List[float]] = []
        y: List[float] = []

        for row in dataset:
            target = row.get("target_pm25_next_hour")
            if target is None:
                continue
            X.append(self.extract_features(row))
            y.append(float(target))

        n_samples = len(y)
        if n_samples == 0:
            raise ValueError("No valid target labels found in dataset")

        # Local gradient descent with normalized error scaling
        for epoch in range(epochs):
            grad_w = [0.0] * len(self.weights)
            grad_b = 0.0

            for xi, yi in zip(X, y):
                pred_val = self.predict_value(xi)
                err = pred_val - yi  # residual
                # Gradient scaled wrt normalized feature scale (45.0)
                norm_err = err / 45.0
                for j in range(len(self.weights)):
                    grad_w[j] += (norm_err * xi[j]) / n_samples
                grad_b += err / n_samples

            # Apply gradients with L2 regularization
            for j in range(len(self.weights)):
                self.weights[j] -= lr * (grad_w[j] + l2_reg * self.weights[j])
            self.bias -= lr * grad_b

        return self.evaluate(dataset)

    def evaluate(self, dataset: List[Dict[str, Any]]) -> Dict[str, float]:
        """Evaluate model against a test or training dataset using real metrics."""
        y_true = []
        y_pred = []

        for row in dataset:
            target = row.get("target_pm25_next_hour")
            if target is None:
                continue
            y_true.append(float(target))
            x = self.extract_features(row)
            y_pred.append(self.predict_value(x))

        if not y_true:
            return {"sample_count": 0.0, "mae": 0.0, "rmse": 0.0, "r2": 0.0}

        n = len(y_true)
        mae = sum(abs(t - p) for t, p in zip(y_true, y_pred)) / n
        mse = sum((t - p) ** 2 for t, p in zip(y_true, y_pred)) / n
        rmse = math.sqrt(mse)

        # R^2 determination coefficient
        mean_y = sum(y_true) / n
        ss_tot = sum((t - mean_y) ** 2 for t in y_true)
        ss_res = sum((t - p) ** 2 for t, p in zip(y_true, y_pred))
        r2 = round(1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0, 4)

        return {
            "sample_count": float(n),
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "r2": r2,
        }

    def get_params(self) -> ModelParams:
        """Export serialized model parameters."""
        return ModelParams(
            feature_names=list(self.feature_names),
            weights=[round(w, 6) for w in self.weights],
            bias=round(self.bias, 4),
            model_version=self.model_version,
        )

    def set_params(self, params: ModelParams) -> None:
        """Load parameters from external ModelParams object."""
        if len(params.weights) != len(self.weights):
            raise ValueError(f"Parameter dimension mismatch: expected {len(self.weights)}, got {len(params.weights)}")
        self.weights = [float(w) for w in params.weights]
        self.bias = float(params.bias)
        self.model_version = params.model_version

    def compute_update_hash(self) -> str:
        """Compute tamper-evident SHA-256 hash digest of parameter vector."""
        payload = json.dumps(
            {
                "weights": [round(w, 6) for w in self.weights],
                "bias": round(self.bias, 4),
                "model_version": self.model_version,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]
