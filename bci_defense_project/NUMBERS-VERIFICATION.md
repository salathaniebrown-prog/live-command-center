# Eagle Eyes / BCI Analytics Numeric Verification

Repository: `salathaniebrown-prog/live-command-center`
Branch: `feature/production-spine-e2e`
Project author field: `Salathaniel Brown Sr` (from repository `package.json`)

This record verifies deterministic calculations from the committed analytics code. The analytics engine is provenance-neutral: the same deterministic functions can process test fixtures or verified observations. The existence of a regression test does **not** mean an externally observed or deployed value was simulated.

## Deterministic results

- Binary signature input `[0.2, 0.8, 0.5]` with thresholds `[0.5, 0.5, 0.5]` -> `(0, 1, 1)`.
- Hamming distance between `(1, 0, 1, 1)` and `(1, 1, 1, 0)` -> `2`.
- Nominal-state input `[0.8, 0.2, 0.9]` with thresholds `[0.5, 0.5, 0.5]` and healthy signature `(1, 0, 1)` -> signature `(1, 0, 1)`, anomaly score `0.0`, status `NOMINAL`.
- Kinematics positions `[[100, 200], [150, 220], [210, 250]]`, `dt=1.0` -> velocity rows `[[50, 20], [55, 25], [60, 30]]`; maximum vector magnitude `67.08203932499369`.
- Hydroacoustic sample `sin(linspace(0, 10, 128))` -> FFT magnitude array with `128` finite, non-negative coefficients.
- Orbital matrices `[[1, 2], [3, 4]]` and `[[5, 6], [7, 8]]` -> product `[[19, 22], [43, 50]]`; deterministic matrix trace `69.0`.

## Classification rule

Classify each emitted metric from its actual source record:

- `VERIFIED` — the input observation has trusted source provenance plus a measurement or retrieval timestamp, and the deterministic calculation is reproducible.
- `DERIVED_VERIFIED` — the output is calculated from verified input observations and preserves their provenance.
- `TEST` — the input is an explicit regression/unit-test fixture.
- `UNKNOWN` — provenance is absent or cannot be verified.

Do **not** relabel a production or externally observed value as `SIMULATED` merely because the same algorithm is also covered by deterministic test fixtures. Conversely, a numeric result must not be promoted to `VERIFIED` solely because the arithmetic passed CI; the source observation still needs its provenance.
