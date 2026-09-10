import numpy as np

from bci_analytics.engine import analyze_state, binary_signature, hamming_distance
from bci_analytics.multi_domain import BCIDefenseEngine


def test_binary_signature():
    result = binary_signature([0.2, 0.8, 0.5], [0.5, 0.5, 0.5])
    assert result == (0, 1, 1)


def test_hamming_distance():
    assert hamming_distance((1, 0, 1, 1), (1, 1, 1, 0)) == 2


def test_nominal_state():
    state = analyze_state(
        features=[0.8, 0.2, 0.9],
        thresholds=[0.5, 0.5, 0.5],
        healthy_signature=(1, 0, 1),
    )
    assert state.status == "NOMINAL"
    assert state.anomaly_score == 0.0


def test_matrix_trace_fixture_score_is_69():
    engine = BCIDefenseEngine(channels=8)
    matrix_a = np.array([[1, 2], [3, 4]], dtype=float)
    matrix_b = np.array([[5, 6], [7, 8]], dtype=float)
    assert engine.process_satellite_orbit_density(matrix_a, matrix_b) == 69.0
