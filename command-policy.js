"use strict";

const OBSERVATION_AUTHORITY = Object.freeze({
  authority: "observation",
  commandEligible: false
});

const PROHIBITED_COMMAND_PATTERNS = [
  /\barm\b/i,
  /\bdisarm\b/i,
  /\btake[ -]?off\b/i,
  /\bland\b/i,
  /\bnavigate\b/i,
  /\bmission\s*(start|upload|execute)\b/i,
  /\bset[_ -]?(mode|position|velocity|attitude|throttle)\b/i,
  /\bgoto\b/i,
  /\bmove\b/i,
  /\bactuate\b/i
];

function isProhibitedCommandName(name) {
  const value = String(name || "").trim();
  return PROHIBITED_COMMAND_PATTERNS.some((pattern) => pattern.test(value));
}

function assertObservationTool(tool) {
  if (!tool || typeof tool !== "object") {
    throw new TypeError("Tool definition must be an object");
  }

  const name = String(tool.name || "").trim();
  if (!name) {
    throw new Error("Tool definition requires a name");
  }

  if (isProhibitedCommandName(name)) {
    throw new Error(`Command-capable tool is not permitted in observation mode: ${name}`);
  }

  return tool;
}

function assertObservationToolset(tools) {
  if (!Array.isArray(tools)) {
    throw new TypeError("Toolset must be an array");
  }

  tools.forEach(assertObservationTool);
  return tools;
}

function markObservationPayload(payload, extra = {}) {
  return {
    ...payload,
    ...OBSERVATION_AUTHORITY,
    provenance: {
      ...(payload && payload.provenance ? payload.provenance : {}),
      ...(extra.provenance || {})
    },
    ...Object.fromEntries(
      Object.entries(extra).filter(([key]) => key !== "provenance")
    )
  };
}

module.exports = {
  OBSERVATION_AUTHORITY,
  PROHIBITED_COMMAND_PATTERNS,
  isProhibitedCommandName,
  assertObservationTool,
  assertObservationToolset,
  markObservationPayload
};
