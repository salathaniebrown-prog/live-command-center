"""XR-ready observation envelope for Eagle Eyes Reality Engine."""

from __future__ import annotations

from typing import Any, Dict


def to_xr_envelope(motion_state: Dict[str, Any]) -> Dict[str, Any]:
    tracks = []
    for track in motion_state.get("tracks", []):
        depth = track.get("depthM")
        tracks.append({
            "id": track["id"],
            "kind": track.get("kind", "unknown"),
            "confidence": track["confidence"],
            "position": {
                "xNormalized": track["center"]["x"],
                "yNormalized": track["center"]["y"],
                "depthMeters": depth,
                "coordinateSpace": "camera-depth-metric" if depth is not None else "camera-normalized",
            },
            "motion": track["motion"],
        })

    return {
        "schemaVersion": "eagle-eyes.reality-xr.v1",
        "simulated": False,
        "observationOnly": True,
        "sourceType": "physical-camera",
        "cameraId": motion_state["cameraId"],
        "capturedAtMs": motion_state["capturedAtMs"],
        "frameIndex": motion_state["frameIndex"],
        "tracks": tracks,
    }
