#!/usr/bin/env node
"use strict";

const dgram = require("node:dgram");

const HOST = process.env.UDP_TELEMETRY_HOST || "127.0.0.1";
const PORT = Number(process.env.UDP_TELEMETRY_PORT || 5050);
const NODE_COUNT = Math.max(1, Number(process.env.SIMULATED_NODE_COUNT || 50));
const ROUNDS = Math.max(1, Number(process.env.SIMULATED_ROUNDS || 10));
const INTERVAL_MS = Math.max(0, Number(process.env.SIMULATED_INTERVAL_MS || 10));

if (HOST !== "127.0.0.1") {
  throw new Error("Load simulation is restricted to 127.0.0.1.");
}

const client = dgram.createSocket("udp4");
let sent = 0;

function send(payload) {
  return new Promise((resolve, reject) => {
    const message = Buffer.from(JSON.stringify(payload));
    client.send(message, PORT, HOST, (error) => {
      if (error) reject(error);
      else resolve();
    });
  });
}

async function main() {
  for (let round = 0; round < ROUNDS; round += 1) {
    for (let node = 1; node <= NODE_COUNT; node += 1) {
      const latencyMs = 4 + ((node * 7 + round * 13) % 140);
      await send({
        nodeId: `sim-node-${String(node).padStart(2, "0")}`,
        simulated: true,
        latencyMs,
        sequence: round * NODE_COUNT + node,
        timestamp: new Date().toISOString()
      });
      sent += 1;
    }

    if (INTERVAL_MS > 0) {
      await new Promise((resolve) => setTimeout(resolve, INTERVAL_MS));
    }
  }

  console.log(
    `Simulation complete: ${sent} explicitly simulated packets sent to ${HOST}:${PORT}.`
  );
}

main()
  .catch((error) => {
    console.error(error.message);
    process.exitCode = 1;
  })
  .finally(() => {
    client.close();
  });
