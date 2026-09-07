# Eagle Eyes ASSM Mesh — Phase 1

ASSM is an additive accelerator layer for Eagle Eyes. Phase 1 consumes Eagle Eyes state records, reuses the existing deterministic 16-feature → 10-D embedding engine, evaluates Hamming-distance variance, and reports metrics without writing back to Eagle Eyes.

## Safety boundary

- Eagle Eyes V13 is upstream and read-only.
- ASSM must not overwrite root Eagle Eyes files.
- Phase 1 performs no financial execution, blockchain signing, production mutation, or autonomous deployment.
- The current router reads newline-delimited JSON from stdin and emits JSON to stdout.
- Scaling to 4/32 workers happens only after single-worker validation.

## Phase 1 flow

```text
Eagle Eyes normalized spine record
          |
          v
     state-adapter
          |
          v
 existing state-embedding.js
          |
          v
      10-D vector
          |
          v
    anomaly-engine
          |
          v
 worker + metrics report
```

## Run

From `assm/`:

```bash
npm run ci
node src/ingest-router.js
```

Then send one normalized Eagle Eyes spine record per line. The first valid record becomes the in-process observation baseline for that run; later records are compared with Hamming distance. No data is persisted.

## Promotion gates

1. Single-worker correctness
2. Throughput and event-loop measurements
3. Four-worker sandbox
4. Packet-loss/backpressure design
5. Thirty-two-worker sandbox
6. Production review
