"use strict";

const STATE_EMBEDDING_VERSION = "eagle-eyes.state-embedding.v1";
const FEATURE_DIM = 16;
const EMBEDDING_DIM = 10;

const PROJECTION = [
  [2, -1, 1, 3, 2, 1, -1, 1, -2, 1, -1, 2, 1, -1, 2, 1],
  [-1, 2, 1, -2, 3, -1, 1, 2, 1, -1, 2, -1, 1, 2, -1, 1],
  [1, 1, -2, 1, -1, 3, 2, -1, 1, 2, -1, 1, -2, 1, 2, -1],
  [2, -2, 1, 1, 1, -1, 3, 2, -1, 1, 2, 1, -1, -2, 1, 2],
  [-2, 1, 2, -1, 2, 1, 1, -3, 2, 1, 1, -1, 2, 1, -1, 2],
  [1, 3, -1, 2, -2, 1, -1, 1, 2, -2, 1, 2, 1, -1, 1, 2],
  [3, 1, 1, -1, 2, -2, 1, 2, -1, 1, -2, 1, 2, 1, -1, 1],
  [-1, 2, 3, 1, -1, 2, -2, 1, 1, -1, 2, -2, 1, 1, 2, -1],
  [2, 1, -1, 2, 1, -2, 3, -1, 2, 1, -1, 1, -2, 2, 1, -1],
  [1, -2, 2, 1, 3, 1, -1, 2, -2, 1, 2, -1, 1, -1, 2, 1]
];

function clamp(value, min = -1, max = 1) {
  return Math.max(min, Math.min(max, value));
}

function finite(value, fallback = 0) {
  return Number.isFinite(value) ? value : fallback;
}

function hashUnit(value) {
  if (!value) return 0;
  let hash = 2166136261;
  for (const char of String(value).toLowerCase()) {
    hash ^= char.charCodeAt(0);
    hash = Math.imul(hash, 16777619) >>> 0;
  }
  return (hash / 0xffffffff) * 2 - 1;
}

function severityScore(value) {
  const key = String(value || "").toLowerCase();
  const known = {
    extreme: 1,
    severe: 0.75,
    moderate: 0.4,
    minor: 0.15,
    unknown: 0
  };
  return key in known ? known[key] : hashUnit(key) * 0.25;
}

function timeMs(value) {
  if (!value) return null;
  const parsed = Date.parse(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function relativeHours(value, reference, scaleHours) {
  const target = timeMs(value);
  const anchor = timeMs(reference);
  if (target === null || anchor === null) return 0;
  return clamp((target - anchor) / (scaleHours * 60 * 60 * 1000));
}

function logUnit(value, scale = 10) {
  const number = finite(value, 0);
  if (number === 0) return 0;
  const sign = Math.sign(number);
  return clamp(sign * Math.log1p(Math.abs(number)) / scale);
}

function extractStateFeatures(record) {
  const position = record?.position || {};
  const metadata = record?.sourceMetadata || {};
  const retrievedAt = record?.retrievedAt || null;

  return [
    hashUnit(record?.source),
    hashUnit(record?.eventType),
    hashUnit(record?.title),
    severityScore(record?.severity),
    clamp(finite(record?.magnitude) / 10),
    clamp(finite(position.latitude) / 90),
    clamp(finite(position.longitude) / 180),
    logUnit(position.depth, 8),
    relativeHours(record?.occurredAt, retrievedAt, 168),
    relativeHours(record?.expiresAt, retrievedAt, 168),
    relativeHours(record?.updatedAt, retrievedAt, 168),
    hashUnit(metadata.urgency),
    hashUnit(metadata.certainty),
    hashUnit(metadata.status),
    clamp(finite(metadata.significance) / 1000),
    hashUnit(record?.geometry?.type)
  ];
}

function project(features) {
  if (!Array.isArray(features) || features.length !== FEATURE_DIM) {
    throw new Error(`Expected ${FEATURE_DIM} embedding features`);
  }

  return PROJECTION.map((row) => {
    const score = row.reduce((sum, weight, index) => sum + weight * features[index], 0);
    return score > 0 ? 1 : 0;
  });
}

function embedSpineRecord(record) {
  const features = extractStateFeatures(record);
  return {
    version: STATE_EMBEDDING_VERSION,
    method: "deterministic-binary-projection",
    trained: false,
    featureDim: FEATURE_DIM,
    dimensions: EMBEDDING_DIM,
    vector: project(features)
  };
}

function hammingDistance(left, right) {
  const a = Array.isArray(left?.vector) ? left.vector : left;
  const b = Array.isArray(right?.vector) ? right.vector : right;
  if (!Array.isArray(a) || !Array.isArray(b) || a.length !== b.length) {
    throw new Error("Embeddings must be equal-length vectors");
  }
  return a.reduce((distance, bit, index) => distance + Number(bit !== b[index]), 0);
}

function decorateNormalizedResult(result) {
  if (!result || !Array.isArray(result.events)) return result;
  return {
    ...result,
    events: result.events.map((event) => {
      if (!event?.spine) return event;
      return {
        ...event,
        spine: {
          ...event.spine,
          stateEmbedding: embedSpineRecord(event.spine)
        }
      };
    })
  };
}

module.exports = {
  STATE_EMBEDDING_VERSION,
  FEATURE_DIM,
  EMBEDDING_DIM,
  extractStateFeatures,
  embedSpineRecord,
  hammingDistance,
  decorateNormalizedResult
};
