"""Deterministic, observation-only BCI state analytics.

This module operates only on supplied numeric feature vectors. It does not
connect to BCI hardware, stimulate a user, diagnose a condition, or authorize
commands.
"""

from dataclasses import dataclass
from math import isfinite
from typing import Sequence


@dataclass(frozen=True)
class BCIState:
    signature: tuple[int, ...]
    anomaly_score: float
    status: str


def _validated_values(values: Sequence[float], name: str) -> tuple[float, ...]:
    normalized = tuple(float(value) for value in values)
    if not normalized:
        raise ValueError(f"{name} must not be empty")
    if not all(isfinite(value) for value in normalized):
        raise ValueError(f"{name} must contain only finite numeric values")
    return normalized


def binary_signature(
    features: Sequence[float],
    thresholds: Sequence[float],
) -> tuple[int, ...]:
    feature_values = _validated_values(features, "features")
    threshold_values = _validated_values(thresholds, "thresholds")

    if len(feature_values) != len(threshold_values):
        raise ValueError("features and thresholds must have equal length")

    return tuple(
        int(value >= threshold)
        for value, threshold in zip(feature_values, threshold_values)
    )


def hamming_distance(
    left: Sequence[int],
    right: Sequence[int],
) -> int:
    left_values = tuple(left)
    right_values = tuple(right)

    if not left_values or not right_values:
        raise ValueError("signatures must not be empty")
    if len(left_values) != len(right_values):
        raise ValueError("signatures must have equal length")
    if any(bit not in (0, 1) for bit in left_values + right_values):
        raise ValueError("signatures must contain only binary values")

    return sum(a != b for a, b in zip(left_values, right_values))


def analyze_state(
    features: Sequence[float],
    thresholds: Sequence[float],
    healthy_signature: Sequence[int],
) -> BCIState:
    signature = binary_signature(features, thresholds)
    healthy = tuple(healthy_signature)

    distance = hamming_distance(signature, healthy)
    anomaly_score = distance / len(signature)

    if anomaly_score == 0:
        status = "NOMINAL"
    elif anomaly_score <= 0.20:
        status = "DEGRADED"
    else:
        status = "ANOMALOUS"

    return BCIState(
        signature=signature,
        anomaly_score=anomaly_score,
        status=status,
    )


def main() -> int:
    """Run a deterministic self-check; this is not a live sensor reader."""
    state = analyze_state(
        features=[0.8, 0.2, 0.9],
        thresholds=[0.5, 0.5, 0.5],
        healthy_signature=(1, 0, 1),
    )
    print(
        "BCI analytics deterministic self-check: "
        f"signature={state.signature} "
        f"anomaly_score={state.anomaly_score:.3f} "
        f"status={state.status}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
