"use strict";

const dgram = require("node:dgram");
const readline = require("node:readline");
const { compileSystemPerformanceMetrics } = require("./src/database/analytics");
const { McpToolFirewall } = require("./src/security/mcpFirewall");

const SERVER_INFO = {
  name: "eagle-eyes-supercomputer-hub",
  version: "2.0.0"
};
const PROTOCOL_VERSION = "2025-06-18";
const CONTROL_HOST = process.env.UDP_CONTROL_HOST || "127.0.0.1";
const CONTROL_PORT = Number(process.env.UDP_CONTROL_PORT || 5051);
const ACK_TIMEOUT_MS = Math.max(250, Number(process.env.MCP_UDP_ACK_TIMEOUT_MS || 1500));
const firewall = new McpToolFirewall();

const TOOLS = [
  {
    name: "get_cluster_metrics",
    description:
      "Reads current host/container metrics and the latest locally observed UDP backplane state. Simulated and live packet counts remain separate.",
    inputSchema: {
      type: "object",
      properties: {},
      additionalProperties: false
    },
    annotations: {
      readOnlyHint: true,
      destructiveHint: false,
      idempotentHint: true,
      openWorldHint: false
    }
  },
  {
    name: "tune_udp_backplane",
    description:
      "Adjusts the local Eagle Eyes UDP processing throttle. Requests are firewall-limited to 0-250ms, rate-limited, sent to loopback only, and require an acknowledgement from the UDP control daemon.",
    inputSchema: {
      type: "object",
      properties: {
        throttleFactor: {
          type: "number",
          minimum: 0,
          maximum: 250,
          description: "Processing delay in milliseconds."
        }
      },
      required: ["throttleFactor"],
      additionalProperties: false
    },
    annotations: {
      readOnlyHint: false,
      destructiveHint: false,
      idempotentHint: false,
      openWorldHint: false
    }
  }
];

function rpcResult(id, result) {
  return { jsonrpc: "2.0", id, result };
}

function rpcError(id, code, message, data) {
  const error = { code, message };
  if (data !== undefined) error.data = data;
  return { jsonrpc: "2.0", id: id ?? null, error };
}

function sendTuneCommand(throttleFactor) {
  if (CONTROL_HOST !== "127.0.0.1") {
    return Promise.reject(
      new Error("MCP UDP control target must remain 127.0.0.1.")
    );
  }

  return new Promise((resolve, reject) => {
    const client = dgram.createSocket("udp4");
    let settled = false;

    const finish = (error, value) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      try {
        client.close();
      } catch {
        // Socket may already be closed.
      }
      if (error) reject(error);
      else resolve(value);
    };

    const timer = setTimeout(() => {
      finish(new Error("UDP backplane did not acknowledge the tuning request."));
    }, ACK_TIMEOUT_MS);

    client.once("error", (error) => finish(error));
    client.once("message", (message, rinfo) => {
      if (rinfo.address !== "127.0.0.1" || rinfo.port !== CONTROL_PORT) {
        return;
      }

      try {
        const response = JSON.parse(message.toString("utf8"));
        if (!response?.ok) {
          finish(new Error(response?.error || "UDP backplane rejected the request."));
          return;
        }
        finish(null, response);
      } catch {
        finish(new Error("UDP backplane returned an invalid acknowledgement."));
      }
    });

    const message = Buffer.from(
      JSON.stringify({ cmd: "THROTTLE", val: throttleFactor })
    );

    client.send(message, CONTROL_PORT, CONTROL_HOST, (error) => {
      if (error) finish(error);
    });
  });
}

async function callTool(name, args = {}) {
  if (name === "get_cluster_metrics") {
    const metrics = await compileSystemPerformanceMetrics();
    return {
      content: [{ type: "text", text: JSON.stringify(metrics, null, 2) }]
    };
  }

  if (name === "tune_udp_backplane") {
    try {
      const validated = firewall.validateTuneRequest(args);
      const acknowledgement = await sendTuneCommand(validated.throttleFactor);
      return {
        content: [
          {
            type: "text",
            text:
              `Verification clear. Local UDP backplane acknowledged ` +
              `${acknowledgement.val}ms throttle at ${acknowledgement.appliedAt}.`
          }
        ]
      };
    } catch (error) {
      return {
        content: [{ type: "text", text: error.message }],
        isError: true
      };
    }
  }

  throw new Error(`Unknown tool: ${name}`);
}

async function handleRequest(message) {
  if (!message || typeof message !== "object" || Array.isArray(message)) {
    return rpcError(null, -32600, "Invalid Request");
  }

  const hasId = Object.prototype.hasOwnProperty.call(message, "id");

  if (message.method === "notifications/initialized" || message.method === "notifications/cancelled") {
    return null;
  }

  if (!hasId) {
    return null;
  }

  if (message.method === "initialize") {
    return rpcResult(message.id, {
      protocolVersion: PROTOCOL_VERSION,
      capabilities: {
        tools: { listChanged: false }
      },
      serverInfo: SERVER_INFO
    });
  }

  if (message.method === "ping") {
    return rpcResult(message.id, {});
  }

  if (message.method === "tools/list") {
    return rpcResult(message.id, { tools: TOOLS });
  }

  if (message.method === "tools/call") {
    const name = message.params?.name;
    const args = message.params?.arguments || {};

    if (typeof name !== "string") {
      return rpcError(message.id, -32602, "Invalid params", "Tool name is required.");
    }

    try {
      return rpcResult(message.id, await callTool(name, args));
    } catch (error) {
      return rpcError(message.id, -32602, "Invalid params", error.message);
    }
  }

  return rpcError(message.id, -32601, "Method not found");
}

async function handleEnvelope(envelope) {
  if (Array.isArray(envelope)) {
    if (!envelope.length) return rpcError(null, -32600, "Invalid Request");
    const results = (await Promise.all(envelope.map(handleRequest))).filter(Boolean);
    return results.length ? results : null;
  }
  return handleRequest(envelope);
}

function writeMessage(message) {
  if (message) {
    process.stdout.write(`${JSON.stringify(message)}\n`);
  }
}

function start() {
  const input = readline.createInterface({
    input: process.stdin,
    crlfDelay: Infinity
  });

  input.on("line", async (line) => {
    if (!line.trim()) return;

    let envelope;
    try {
      envelope = JSON.parse(line);
    } catch {
      writeMessage(rpcError(null, -32700, "Parse error"));
      return;
    }

    try {
      writeMessage(await handleEnvelope(envelope));
    } catch (error) {
      console.error(`[mcp] request handling error: ${error.message}`);
      writeMessage(rpcError(envelope?.id ?? null, -32603, "Internal error"));
    }
  });

  console.error(
    `[mcp] ${SERVER_INFO.name} ${SERVER_INFO.version} online over stdio (${PROTOCOL_VERSION}).`
  );
}

if (require.main === module) {
  start();
}

module.exports = {
  PROTOCOL_VERSION,
  SERVER_INFO,
  TOOLS,
  callTool,
  handleEnvelope,
  handleRequest,
  sendTuneCommand,
  start
};
