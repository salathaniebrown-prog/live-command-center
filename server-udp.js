"use strict";

const dgram = require("node:dgram");
const fs = require("node:fs/promises");
const path = require("node:path");

const HOST = process.env.UDP_BIND_HOST || "127.0.0.1";
const TELEMETRY_PORT = Number(process.env.UDP_TELEMETRY_PORT || 5050);
const CONTROL_PORT = Number(process.env.UDP_CONTROL_PORT || 5051);
const MAX_PENDING_PACKETS = Math.max(
  1,
  Number(process.env.UDP_MAX_PENDING_PACKETS || 10000)
);
const LATENCY_SPIKE_MS = Math.max(
  1,
  Number(process.env.UDP_LATENCY_SPIKE_MS || 100)
);
const STATE_PATH =
  process.env.UDP_STATE_PATH ||
  path.join(process.cwd(), "data", "v1", "udp-backplane-state.json");

function requireLoopbackHost(host) {
  if (host !== "127.0.0.1" && process.env.UDP_ALLOW_NON_LOOPBACK !== "1") {
    throw new Error(
      "UDP_BIND_HOST must remain 127.0.0.1 unless UDP_ALLOW_NON_LOOPBACK=1 is explicitly configured."
    );
  }
}

function validateControlCommand(payload) {
  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new Error("Control payload must be an object.");
  }

  if (payload.cmd !== "THROTTLE") {
    throw new Error("Unsupported control command.");
  }

  if (
    typeof payload.val !== "number" ||
    !Number.isFinite(payload.val) ||
    payload.val < 0 ||
    payload.val > 250
  ) {
    throw new Error("Throttle value must be a finite number from 0 to 250ms.");
  }

  return payload.val;
}

function makeState() {
  return {
    startedAt: new Date().toISOString(),
    throttleFactorMs: 0,
    livePackets: 0,
    simulatedPackets: 0,
    rejectedPackets: 0,
    bytesReceived: 0,
    pendingPackets: 0,
    latencySamples: 0,
    latencyTotalMs: 0,
    maxLatencyMs: null,
    latencySpikeCount: 0,
    lastPacketAt: null,
    liveNodes: new Set(),
    simulationNodes: new Set()
  };
}

function snapshotState(state) {
  const averageLatencyMs = state.latencySamples
    ? Number((state.latencyTotalMs / state.latencySamples).toFixed(2))
    : null;

  return {
    startedAt: state.startedAt,
    throttleFactorMs: state.throttleFactorMs,
    liveObservedNodes: state.liveNodes.size,
    simulationObservedNodes: state.simulationNodes.size,
    livePackets: state.livePackets,
    simulatedPackets: state.simulatedPackets,
    rejectedPackets: state.rejectedPackets,
    bytesReceived: state.bytesReceived,
    pendingPackets: state.pendingPackets,
    averageLatencyMs,
    maxLatencyMs: state.maxLatencyMs,
    latencySpikeCount: state.latencySpikeCount,
    lastPacketAt: state.lastPacketAt,
    timestamp: new Date().toISOString()
  };
}

function createBackplane() {
  requireLoopbackHost(HOST);

  const telemetrySocket = dgram.createSocket("udp4");
  const controlSocket = dgram.createSocket("udp4");
  const state = makeState();
  let persistTimer = null;
  let closing = false;

  async function persistState() {
    persistTimer = null;
    try {
      await fs.mkdir(path.dirname(STATE_PATH), { recursive: true });
      await fs.writeFile(
        STATE_PATH,
        `${JSON.stringify(snapshotState(state), null, 2)}\n`,
        "utf8"
      );
    } catch (error) {
      console.error(`[udp] state persistence failed: ${error.message}`);
    }
  }

  function schedulePersist() {
    if (!persistTimer) {
      persistTimer = setTimeout(persistState, 250);
      persistTimer.unref?.();
    }
  }

  function recordTelemetry(message, rinfo) {
    state.pendingPackets = Math.max(0, state.pendingPackets - 1);
    state.bytesReceived += rinfo.size;
    state.lastPacketAt = new Date().toISOString();

    let payload;
    try {
      payload = JSON.parse(message.toString("utf8"));
    } catch {
      state.rejectedPackets += 1;
      schedulePersist();
      return;
    }

    if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
      state.rejectedPackets += 1;
      schedulePersist();
      return;
    }

    const simulated = payload.simulated === true;
    const nodeId =
      typeof payload.nodeId === "string" && payload.nodeId.length <= 128
        ? payload.nodeId
        : null;

    if (simulated) {
      state.simulatedPackets += 1;
      if (nodeId) state.simulationNodes.add(nodeId);
    } else {
      state.livePackets += 1;
      if (nodeId) state.liveNodes.add(nodeId);
    }

    if (typeof payload.latencyMs === "number" && Number.isFinite(payload.latencyMs)) {
      const latency = Math.max(0, payload.latencyMs);
      state.latencySamples += 1;
      state.latencyTotalMs += latency;
      state.maxLatencyMs =
        state.maxLatencyMs === null ? latency : Math.max(state.maxLatencyMs, latency);
      if (latency >= LATENCY_SPIKE_MS) state.latencySpikeCount += 1;
    }

    schedulePersist();
  }

  telemetrySocket.on("message", (message, rinfo) => {
    if (state.pendingPackets >= MAX_PENDING_PACKETS) {
      state.rejectedPackets += 1;
      schedulePersist();
      return;
    }

    state.pendingPackets += 1;

    if (state.throttleFactorMs > 0) {
      setTimeout(
        () => recordTelemetry(message, rinfo),
        state.throttleFactorMs
      );
    } else {
      recordTelemetry(message, rinfo);
    }
  });

  telemetrySocket.on("error", (error) => {
    console.error(`[udp] telemetry socket error: ${error.message}`);
  });

  controlSocket.on("message", (message, rinfo) => {
    let response;

    try {
      if (rinfo.address !== "127.0.0.1") {
        throw new Error("Control commands are accepted from loopback only.");
      }

      const payload = JSON.parse(message.toString("utf8"));
      const throttle = validateControlCommand(payload);
      state.throttleFactorMs = throttle;
      schedulePersist();

      response = {
        ok: true,
        cmd: "THROTTLE",
        val: throttle,
        appliedAt: new Date().toISOString()
      };
    } catch (error) {
      response = {
        ok: false,
        error: error.message,
        timestamp: new Date().toISOString()
      };
    }

    const encoded = Buffer.from(JSON.stringify(response));
    controlSocket.send(encoded, rinfo.port, rinfo.address, (error) => {
      if (error) {
        console.error(`[udp] control acknowledgement failed: ${error.message}`);
      }
    });
  });

  controlSocket.on("error", (error) => {
    console.error(`[udp] control socket error: ${error.message}`);
  });

  async function close() {
    if (closing) return;
    closing = true;
    if (persistTimer) clearTimeout(persistTimer);
    await persistState();
    await Promise.all(
      [telemetrySocket, controlSocket].map(
        (socket) =>
          new Promise((resolve) => {
            try {
              socket.close(resolve);
            } catch {
              resolve();
            }
          })
      )
    );
  }

  return {
    start() {
      telemetrySocket.bind(TELEMETRY_PORT, HOST, () => {
        console.error(`[udp] telemetry listening on ${HOST}:${TELEMETRY_PORT}`);
      });
      controlSocket.bind(CONTROL_PORT, HOST, () => {
        console.error(`[udp] control listening on ${HOST}:${CONTROL_PORT}`);
      });
    },
    close,
    state
  };
}

if (require.main === module) {
  const backplane = createBackplane();
  backplane.start();

  const shutdown = async () => {
    await backplane.close();
    process.exit(0);
  };

  process.once("SIGINT", shutdown);
  process.once("SIGTERM", shutdown);
}

module.exports = {
  createBackplane,
  makeState,
  snapshotState,
  validateControlCommand
};
