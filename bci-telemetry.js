"use strict";

function configured(value) {
  return Boolean(String(value || "").trim());
}

function bciTelemetryStatus(env = process.env) {
  const ingestConfigured = configured(env.BCI_TELEMETRY_INGEST_TOKEN);
  const deviceProfile = String(env.BCI_DEVICE_PROFILE || "unconfigured")
    .trim()
    .slice(0, 80) || "unconfigured";

  return {
    ok: true,
    status: ingestConfigured ? "WAITING" : "UNCONFIGURED",
    source: "bci-telemetry",
    deviceProfile,
    observationOnly: true,
    commandAuthority: false,
    medicalDevice: false,
    diagnosis: false,
    controlOutput: false,
    ingestConfigured,
    message: ingestConfigured
      ? "BCI telemetry lane is configured and waiting for validated read-only observations."
      : "BCI telemetry lane is registered but locked until BCI_TELEMETRY_INGEST_TOKEN is configured.",
    timestamp: new Date().toISOString()
  };
}

module.exports = {
  bciTelemetryStatus
};
