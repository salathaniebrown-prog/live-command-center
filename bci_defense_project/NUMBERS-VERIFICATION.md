# Eagle Eyes / BCI Analytics Numeric Verification

Repository: `salathaniebrown-prog/live-command-center`
Branch: `feature/production-spine-e2e`
Project author field: `Salathaniel Brown Sr` (from repository `package.json`)

This record verifies deterministic calculations from the committed analytics code. It is not a claim of hardware certification or live-sensor provenance by itself.

## Deterministic results

- Binary signature input `[0.2, 0.8, 0.5]` with thresholds `[0.5, 0.5, 0.5]` -> `(0, 1, 1)`.
- Hamming distance between `(1, 0, 1, 1)` and `(1, 1, 1, 0)` -> `2`.
- Nominal-state input `[0.8, 0.2, 0.9]` with thresholds `[0.5, 0.5, 0.5]` and healthy signature `(1, 0, 1)` -> signature `(1, 0, 1)`, anomaly score `0.0`, status `NOMINAL`.
- Kinematics positions `[[100, 200], [150, 220], [210, 250]]`, `dt=1.0` -> velocity rows `[[50, 20], [55, 25], [60, 30]]`; maximum vector magnitude `67.08203932499369`.
- Hydroacoustic sample `sin(linspace(0, 10, 128))` -> FFT magnitude array with `128` finite, non-negative bins.
- Orbital matrices `[[1, 2], [3, 4]]` and `[[5, 6], [7, 8]]` -> product `[[19, 22], [43, 50]]`; trace/orbital score `69.0`.

## Provenance rule

A numeric value should be labeled `VERIFIED` in Eagle Eyes only when its input source and measurement/retrieval timestamp are attached. Deterministic test fixtures are verified calculations, but they are distinct from live hardware or sensor observations.
