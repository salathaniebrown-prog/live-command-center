"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const { ProviderHealthRegistry } = require("../provider-health");

test("auto mode prefers configured OpenAI first", () => {
  const registry = new ProviderHealthRegistry({
    env: {
      OPENAI_API_KEY: "configured",
      ANTHROPIC_API_KEY: "configured"
    },
    now: () => 1_000
  });

  assert.equal(registry.selectProvider("auto"), "openai");
});

test("auto mode falls back to Anthropic during OpenAI cooldown", () => {
  let now = 1_000;
  const registry = new ProviderHealthRegistry({
    env: {
      OPENAI_API_KEY: "configured",
      ANTHROPIC_API_KEY: "configured"
    },
    cooldownMs: 30_000,
    now: () => now
  });

  registry.recordFailure("openai", new Error("temporary provider failure"));

  assert.equal(registry.selectProvider("auto"), "anthropic");

  now += 31_000;
  assert.equal(registry.selectProvider("auto"), "openai");
});

test("explicit provider selection never chooses an unconfigured provider", () => {
  const registry = new ProviderHealthRegistry({
    env: { OPENAI_API_KEY: "configured" },
    now: () => 1_000
  });

  assert.equal(registry.selectProvider("anthropic"), null);
});

test("health report is observation-only and exposes no credential values", () => {
  const secret = "do-not-leak";
  const registry = new ProviderHealthRegistry({
    env: {
      OPENAI_API_KEY: secret,
      OPENAI_MODEL: "gpt-5.6"
    },
    now: () => 1_000
  });

  const report = registry.report();
  const serialized = JSON.stringify(report);

  assert.equal(report.authority, "observation");
  assert.equal(report.commandEligible, false);
  assert.equal(report.ok, true);
  assert.equal(serialized.includes(secret), false);
});
