"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  PROTOCOL_VERSION,
  TOOLS,
  handleRequest
} = require("../server-mcp");

test("MCP broker advertises metrics and guarded tuning tools", () => {
  assert.deepEqual(
    TOOLS.map((tool) => tool.name),
    ["get_cluster_metrics", "tune_udp_backplane"]
  );
  const tune = TOOLS.find((tool) => tool.name === "tune_udp_backplane");
  assert.equal(tune.inputSchema.properties.throttleFactor.maximum, 250);
  assert.equal(tune.inputSchema.additionalProperties, false);
});

test("MCP broker completes initialization with tool capability", async () => {
  const response = await handleRequest({
    jsonrpc: "2.0",
    id: 1,
    method: "initialize",
    params: { protocolVersion: PROTOCOL_VERSION }
  });

  assert.equal(response.id, 1);
  assert.equal(response.result.protocolVersion, PROTOCOL_VERSION);
  assert.deepEqual(response.result.capabilities.tools, { listChanged: false });
});

test("MCP broker lists tools through JSON-RPC", async () => {
  const response = await handleRequest({
    jsonrpc: "2.0",
    id: 2,
    method: "tools/list",
    params: {}
  });
  assert.equal(response.result.tools.length, 2);
});
