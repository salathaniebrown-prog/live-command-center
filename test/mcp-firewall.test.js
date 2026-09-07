"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { McpToolFirewall } = require("../src/security/mcpFirewall");

test("MCP firewall accepts bounded numeric throttle values", () => {
  const firewall = new McpToolFirewall({ cooldownMs: 0 });
  assert.equal(firewall.validateTuneRequest({ throttleFactor: 0 }).throttleFactor, 0);
  assert.equal(firewall.validateTuneRequest({ throttleFactor: 250 }).throttleFactor, 250);
});

test("MCP firewall rejects malformed and out-of-range values", () => {
  const firewall = new McpToolFirewall({ cooldownMs: 0 });
  for (const throttleFactor of [-1, 251, "50", true, NaN, Infinity]) {
    assert.throws(() => firewall.validateTuneRequest({ throttleFactor }));
  }
  assert.throws(() =>
    firewall.validateTuneRequest({ throttleFactor: 10, extra: "not-allowed" })
  );
});

test("MCP firewall blocks rapid repeat execution", () => {
  const firewall = new McpToolFirewall({ cooldownMs: 5000 });
  firewall.validateTuneRequest({ throttleFactor: 10 });
  assert.throws(
    () => firewall.validateTuneRequest({ throttleFactor: 10 }),
    /Execution throttled/
  );
});
