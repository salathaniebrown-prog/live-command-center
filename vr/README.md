# Eagle Eyes VR Baseline v1

This directory freezes the recovered Eagle Eyes VR baseline without changing production `main` behavior.

## Baseline truth policy

- Observation-only.
- No simulated telemetry.
- Live public feeds use the real NWS active alerts, USGS all-day earthquake GeoJSON, and NASA EONET open-events endpoints.
- SQLite fallback is allowed only as historical continuity and must be displayed as `STALE_CACHE` / `LOCAL_SQLITE_CACHE`.
- Vehicle command authority is `NONE`.
- OpenXR module detection does **not** equal native headset rendering.

## What works in this frozen baseline

- Python source compiles successfully with `python -m py_compile`.
- SQLite WAL telemetry cache and DB health state.
- Live feed counts and freshness/source labels.
- Memory RSS and growth watchdog telemetry.
- Smoothed render FPS.
- Desktop Pyglet HUD fallback.
- OpenXR availability status without falsely creating an XR session that lacks a platform graphics binding.

## Native OpenXR work still required

Do not mark XR as native/live until all of these are implemented and validated on the actual host/runtime:

1. Platform-specific graphics binding (for example Win32/WGL or the correct Linux binding).
2. OpenXR event polling and session-state transitions.
3. `xrBeginSession` / `xrEndSession` lifecycle.
4. Runtime-selected swapchain formats and recommended view sizes.
5. Swapchain image enumeration and OpenGL framebuffer attachment.
6. `xrLocateViews` for left/right eye poses and FOV.
7. Per-eye projection/view matrices.
8. `XrCompositionLayerProjectionView` submission through `xrEndFrame`.
9. Runtime loss / headset removal recovery back to desktop mode.

## PX4 / serial hardware preflight

This is separate from OpenXR. On the machine connected to the PX4/autopilot, use:

```bash
ls -l /dev/serial/by-id/ 2>/dev/null || ls -l /dev/tty* | grep -E "USB|ACM"
```

Prefer a stable `/dev/serial/by-id/...` path over `/dev/ttyUSB0` or `/dev/ttyACM0` when wiring the existing observation-only MAVLink bridge.

## Acceptance target

> Eagle Eyes VR shows real live telemetry in a genuine headset-rendered HUD without breaking desktop fallback.

The first native-XR smoke test should prove only that target. Do not add BCI, control authority, synthetic telemetry, or additional actuation into this baseline.
