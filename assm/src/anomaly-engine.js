"use strict";

const { distanceBetween } = require("./state-adapter");

function analyzeAgainstBaseline(candidateEnvelope, baselineEnvelope, threshold = 5) {
  if (!baselineEnvelope) {
    return {
      baselineEstablished: true,
      anomalous: false,
      distance: 0,
      threshold
    };
  }

  const distance = distanceBetween(candidateEnvelope, baselineEnvelope);
  return {
    baselineEstablished: false,
    anomalous: distance >= threshold,
    distance,
    threshold
  };
}

module.exports = {
  analyzeAgainstBaseline
};
