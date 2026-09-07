"""Temporal motion calculations for validated physical-camera observations."""

from .contracts import validate_reality_frame


class MotionTracker:
    def __init__(self):
        self.previous = {}

    def process(self, frame):
        validate_reality_frame(frame)
        now_ms = frame["capturedAtMs"]
        tracks_out = []

        for track in frame["tracks"]:
            prior = self.previous.get(track["id"])
            motion = {
                "dxNormalized": 0.0,
                "dyNormalized": 0.0,
                "speedNormalizedPerSec": 0.0,
                "depthDeltaM": None,
                "moving": False,
            }

            if prior is not None:
                dt_ms = now_ms - prior["capturedAtMs"]
                if dt_ms > 0:
                    dt_sec = dt_ms / 1000.0
                    dx = float(track["center"]["x"]) - float(prior["center"]["x"])
                    dy = float(track["center"]["y"]) - float(prior["center"]["y"])
                    speed = ((dx * dx + dy * dy) ** 0.5) / dt_sec
                    motion.update({
                        "dxNormalized": dx,
                        "dyNormalized": dy,
                        "speedNormalizedPerSec": speed,
                        "moving": speed > 0.01,
                    })
                    if track.get("depthM") is not None and prior.get("depthM") is not None:
                        motion["depthDeltaM"] = float(track["depthM"]) - float(prior["depthM"])

            tracks_out.append({**track, "motion": motion})
            self.previous[track["id"]] = {
                "capturedAtMs": now_ms,
                "center": dict(track["center"]),
                "depthM": track.get("depthM"),
            }

        return {
            "ok": True,
            "simulated": False,
            "observationOnly": True,
            "cameraId": frame["cameraId"],
            "capturedAtMs": now_ms,
            "frameIndex": frame["frameIndex"],
            "tracks": tracks_out,
        }
