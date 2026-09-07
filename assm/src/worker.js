"use strict";

const { toStateEnvelope } = require("./state-adapter");
const { analyzeAgainstBaseline } = require("./anomaly-engine");

function processRecord(record, context) {
  const envelope = toStateEnvelope(record);
  const analysis = analyzeAgainstBaseline(
    envelope,
    context.baseline,
    context.threshold
  );

  if (!context.baseline) {
    context.baseline = envelope;
  }

  context.metrics.recordProcessed({ anomalous: analysis.anomalous });

  return {
    ok: true,
    readOnly: true,
    persisted: false,
    stateEmbedding: envelope.stateEmbedding,
    analysis,
    metrics: context.metrics.snapshot()
  };
}

module.exports = { processRecord };
