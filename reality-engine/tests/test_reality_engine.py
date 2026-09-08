import unittest

from reality_engine import MotionTracker, validate_reality_frame, to_xr_envelope


def frame(index, x, y, depth=None, simulated=False):
    track = {
        "id": "person-1",
        "kind": "person",
        "confidence": 0.99,
        "center": {"x": x, "y": y},
    }
    if depth is not None:
        track["depthM"] = depth
    return {
        "schemaVersion": "eagle-eyes.reality-frame.v1",
        "simulated": simulated,
        "sourceType": "camera",
        "cameraId": "physical-camera-1",
        "capturedAtMs": 1000 + index * 100,
        "frameIndex": index,
        "width": 1920,
        "height": 1080,
        "tracks": [track],
    }


class RealityEngineTests(unittest.TestCase):
    def test_simulated_frames_are_rejected(self):
        with self.assertRaises(ValueError):
            validate_reality_frame(frame(0, 0.5, 0.5, simulated=True))

    def test_motion_is_derived_from_consecutive_real_frames(self):
        tracker = MotionTracker()
        first = tracker.process(frame(0, 0.5, 0.5, 2.0))
        second = tracker.process(frame(1, 0.6, 0.5, 1.8))
        self.assertFalse(first["tracks"][0]["motion"]["moving"])
        self.assertTrue(second["tracks"][0]["motion"]["moving"])
        self.assertAlmostEqual(second["tracks"][0]["motion"]["dxNormalized"], 0.1)
        self.assertAlmostEqual(second["tracks"][0]["motion"]["depthDeltaM"], -0.2)

    def test_xr_output_preserves_real_only_truth_state(self):
        tracker = MotionTracker()
        state = tracker.process(frame(0, 0.25, 0.75))
        envelope = to_xr_envelope(state)
        self.assertIs(envelope["simulated"], False)
        self.assertIs(envelope["observationOnly"], True)
        self.assertEqual(envelope["tracks"][0]["position"]["coordinateSpace"], "camera-normalized")


if __name__ == "__main__":
    unittest.main()
