"""Strict real-camera data contract for Eagle Eyes Reality Engine."""

from __future__ import annotations

import math
from typing import Any, Dict

REALITY_SCHEMA_VERSION = "eagle-eyes.reality-frame.v1"
_ALLOWED_KINDS = {"person", "object", "unknown"}


def _finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _normalized(value: Any) -> bool:
    return _finite_number(value) and 0.0 <= float(value) <= 1.0


def validate_reality_frame(frame: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(frame, dict):
        raise ValueError("reality frame must be an object")
    if frame.get("schemaVersion") != REALITY_SCHEMA_VERSION:
        raise ValueError(f"schemaVersion must be {REALITY_SCHEMA_VERSION}")
    if frame.get("simulated") is not False:
        raise ValueError("Reality Engine accepts real camera observations only")
    if frame.get("sourceType") != "camera":
        raise ValueError("sourceType must be camera")

    camera_id = frame.get("cameraId")
    if not isinstance(camera_id, str) or not camera_id.strip() or len(camera_id.strip()) > 128:
        raise ValueError("cameraId is required and must be at most 128 characters")

    captured_at_ms = frame.get("capturedAtMs")
    if not isinstance(captured_at_ms, int) or isinstance(captured_at_ms, bool) or captured_at_ms <= 0:
        raise ValueError("capturedAtMs must be a positive integer")

    frame_index = frame.get("frameIndex")
    if not isinstance(frame_index, int) or isinstance(frame_index, bool) or frame_index < 0:
        raise ValueError("frameIndex must be a non-negative integer")

    for field in ("width", "height"):
        value = frame.get(field)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{field} must be a positive integer")

    tracks = frame.get("tracks")
    if not isinstance(tracks, list):
        raise ValueError("tracks must be an array")

    seen_ids = set()
    for track in tracks:
        if not isinstance(track, dict):
            raise ValueError("each track must be an object")
        track_id = track.get("id")
        if not isinstance(track_id, str) or not track_id.strip() or len(track_id.strip()) > 128:
            raise ValueError("track.id is required and must be at most 128 characters")
        if track_id in seen_ids:
            raise ValueError("track ids must be unique within a frame")
        seen_ids.add(track_id)

        kind = track.get("kind", "unknown")
        if kind not in _ALLOWED_KINDS:
            raise ValueError("track.kind must be person, object, or unknown")

        confidence = track.get("confidence")
        if not _normalized(confidence):
            raise ValueError("track.confidence must be between 0 and 1")

        center = track.get("center")
        if not isinstance(center, dict) or not _normalized(center.get("x")) or not _normalized(center.get("y")):
            raise ValueError("track.center.x/y must be normalized camera coordinates")

        depth = track.get("depthM")
        if depth is not None and (not _finite_number(depth) or float(depth) <= 0):
            raise ValueError("track.depthM must be a positive finite number when supplied")

    return frame
