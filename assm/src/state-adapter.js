"use strict";

const {
  embedSpineRecord,
  hammingDistance
} = require("../../state-embedding");

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function validateSpineRecord(record) {
  if (!isObject(record)) {
    throw new TypeError("ASSM expected an Eagle Eyes spine record object");
  }
  return record;
}

function toStateEnvelope(record) {
  const spine = validateSpineRecord(record);
  return {
    source: "eagle-eyes",
    readOnly: true,
    persisted: false,
    observedAt: new Date().toISOString(),
    spine,
    stateEmbedding: embedSpineRecord(spine)
  };
}

function distanceBetween(leftEnvelope, rightEnvelope) {
  return hammingDistance(
    leftEnvelope?.stateEmbedding,
    rightEnvelope?.stateEmbedding
  );
}

module.exports = {
  validateSpineRecord,
  toStateEnvelope,
  distanceBetween
};
