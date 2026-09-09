import numpy as np

from bci_analytics.engine import analyze_state, binary_signature, hamming_distance
from bci_analytics.multi_domain import BCIDefenseEngine


ARCH_HEALTHY_SIGNATURE = (1, 0, 1, 1, 0, 1, 0, 1, 1, 0)
ARCH_THRESHOLDS = [0.5] * 10


def _features_for_signature(signature):
    return [0.9 if bit else 0.1 for bit in signature]


def test_signature_contract():
    assert binary_signature(
        [0.2, 0.8, 0.5],
        [0.5, 0.5, 0.5],
    ) == (0, 1, 1)


def test_hamming_contract():
    assert hamming_distance(
        (1, 0, 1, 1),
        (1, 1, 1, 0),
    ) == 2


def test_nominal_anomaly_contract():
    state = analyze_state(
        features=[0.8, 0.2, 0.9],
        thresholds=[0.5, 0.5, 0.5],
        healthy_signature=(1, 0, 1),
    )
    assert state.signature == (1, 0, 1)
    assert state.anomaly_score == 0.0
    assert state.status == "NOMINAL"


def test_10_bit_architecture_anomaly_bands():
    nominal = analyze_state(
        features=_features_for_signature(ARCH_HEALTHY_SIGNATURE),
        thresholds=ARCH_THRESHOLDS,
        healthy_signature=ARCH_HEALTHY_SIGNATURE,
    )
    assert nominal.anomaly_score == 0.0
    assert nominal.status == "NOMINAL"

    one_bit = (1, 0, 1, 1, 0, 1, 0, 1, 1, 1)
    degraded_10 = analyze_state(
        features=_features_for_signature(one_bit),
        thresholds=ARCH_THRESHOLDS,
        healthy_signature=ARCH_HEALTHY_SIGNATURE,
    )
    assert hamming_distance(one_bit, ARCH_HEALTHY_SIGNATURE) == 1
    assert degraded_10.anomaly_score == 0.1
    assert degraded_10.status == "DEGRADED"

    two_bits = (1, 0, 1, 1, 0, 1, 0, 1, 0, 1)
    degraded_20 = analyze_state(
        features=_features_for_signature(two_bits),
        thresholds=ARCH_THRESHOLDS,
        healthy_signature=ARCH_HEALTHY_SIGNATURE,
    )
    assert hamming_distance(two_bits, ARCH_HEALTHY_SIGNATURE) == 2
    assert degraded_20.anomaly_score == 0.2
    assert degraded_20.status == "DEGRADED"

    three_bits = (1, 0, 1, 1, 0, 1, 0, 0, 0, 1)
    anomalous_30 = analyze_state(
        features=_features_for_signature(three_bits),
        thresholds=ARCH_THRESHOLDS,
        healthy_signature=ARCH_HEALTHY_SIGNATURE,
    )
    assert hamming_distance(three_bits, ARCH_HEALTHY_SIGNATURE) == 3
    assert anomalous_30.anomaly_score == 0.3
    assert anomalous_30.status == "ANOMALOUS"


def test_kinematics_contract():
    engine = BCIDefenseEngine(channels=8)
    positions = np.array(
        [[100, 200], [150, 220], [210, 250]],
        dtype=float,
    )
    velocities = engine.process_airforce_kinematics(positions, dt=1.0)
    expected = np.array(
        [[50, 20], [55, 25], [60, 30]],
        dtype=float,
    )
    np.testing.assert_allclose(velocities, expected)
    max_velocity = float(np.linalg.norm(velocities, axis=1).max())
    assert np.isclose(max_velocity, 67.08203932499369)


def test_fft_contract():
    engine = BCIDefenseEngine(channels=8)
    signal = np.sin(np.linspace(0, 10, 128))
    spectrum = engine.process_submarine_hydroacoustics(signal)
    assert spectrum.shape == (128,)
    assert np.all(np.isfinite(spectrum))
    assert np.all(spectrum >= 0)


def test_orbital_matrix_trace_fixture_contract():
    engine = BCIDefenseEngine(channels=8)
    matrix_a = np.array([[1, 2], [3, 4]], dtype=float)
    matrix_b = np.array([[5, 6], [7, 8]], dtype=float)
    product = matrix_a @ matrix_b
    np.testing.assert_allclose(product, np.array([[19, 22], [43, 50]], dtype=float))
    assert engine.process_satellite_orbit_density(matrix_a, matrix_b) == 69.0
