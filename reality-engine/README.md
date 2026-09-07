# Eagle Eyes Reality Engine — Phase 1

Real-world motion/spatial bridge for Eagle Eyes.

## Truth boundary

This phase does **not** claim a camera is connected. It defines and validates the data contract that a real camera/tracker must satisfy before Eagle Eyes accepts motion state.

- Real capture only: `simulated` must be exactly `false`.
- Source type must be `camera`.
- No generated/mock frames are accepted by the validator.
- No production writes, device control, or vehicle authority.
- No website is the sensor. The future sensor adapter must bind to physical camera hardware.
- XR output is observation-only.

## Flow

```text
PHYSICAL CAMERA / MOTION SENSOR
        |
        v
real capture adapter   (next hardware milestone)
        |
        v
Reality Frame Contract
        |
        +--> real-only validation
        +--> per-track motion state
        +--> optional depth state
        |
        v
XR-ready Reality Envelope
        |
        v
Eagle Eyes VR / OpenXR
```

## Phase 1 modules

- `reality_engine/contracts.py` — strict real-camera frame/track validation.
- `reality_engine/motion.py` — derives temporal motion from consecutive real observations.
- `reality_engine/xr.py` — converts validated state to an observation-only XR envelope.
- `tests/test_reality_engine.py` — rejects simulated input and verifies deterministic motion/XR output.

## Coordinate truth

Without calibrated depth, X/Y remain normalized camera-image coordinates. The engine does not pretend they are meters. If a real depth-capable camera supplies finite `depthM`, that value is carried explicitly as measured depth.

## Next hardware milestone

Bind one physical camera or depth camera, emit `eagle-eyes.reality-frame.v1` frames, and prove live motion from a person/object in front of that camera. Only after that passes should OpenXR rendering consume the stream.
