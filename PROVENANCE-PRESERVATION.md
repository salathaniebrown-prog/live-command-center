# Eagle Eyes Provenance Preservation Snapshot

Repository: `salathaniebrown-prog/live-command-center`

Purpose: preserve a verifiable record of the divergent production and feature histories before reconciliation. This document does not allege misconduct by any person; it records repository state so authorship, calculations, and missing-file questions can be resolved from Git history.

## Snapshot

- Main head observed: `989b0357d8eb381b9268bdcf1ae0f2b5b580143c`
- Feature head observed before this snapshot: `9c0eb072ecfba3536764b2a6569bcac1f2f5f75a`
- Common ancestor: `79be7584cc5f996639d25217d81b863ec3fb4fe7`
- Branch: `feature/production-spine-e2e`
- Repository account: `salathaniebrown-prog`
- Project author field in `package.json`: `Salathaniel Brown Sr`

## Divergence observed

At the time of comparison, `main` contained 3 commits not present on the feature branch, while the feature branch contained 14 commits not present on `main`.

Main-only changed surface observed:

- `MASTER-BUILD.md`
- `public/index.html`
- `public/workspace.css`
- `public/workspace.js`
- `test/workspace.test.js`

The feature branch contains the BCI analytics/numeric verification work and its dedicated CI gate. These histories must be reconciled without deleting either side.

## Numeric CI evidence

GitHub Actions run `34373220842` executed the BCI Defense CI on commit `01bd690d7cc0396d15075a34f92e5b1d9563a534` and completed successfully with 10/10 pytest tests passing.

The deterministic checks include:

- binary signature calculation
- Hamming-distance calculation
- nominal anomaly classification
- kinematics gradient calculation
- FFT shape/finite/non-negative validation
- matrix trace fixture `69.0`

The numeric fixture results are reproducible calculations. A runtime value is labeled `VERIFIED` only when its input provenance and measurement/retrieval timestamp are attached.

## Reconciliation rule

1. Do not force-reset either branch.
2. Do not delete main-only workspace files to make the feature branch appear current.
3. Do not delete feature-only analytics/provenance files to make main appear current.
4. Reconcile through a visible pull request with CI evidence.
5. Prefer a merge commit over squashing when preserving commit-level provenance is important.
6. Treat Git commit hashes and GitHub Actions logs as the primary technical evidence of repository history.
