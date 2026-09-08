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

test("auto mode prefers Moonshot Kimi before Anthropic when OpenAI cools down", () => {
  let now = 1_000;
  const registry = new ProviderHealthRegistry({
    env: {
      OPENAI_API_KEY: "configured",
      MOONSHOT_API_KEY: "configured",
      ANTHROPIC_API_KEY: "configured"
    },
    cooldownMs: 30_000,
    now: () => now
  });

  registry.recordFailure("openai", new Error("temporary provider failure"));

  assert.equal(registry.selectProvider("auto"), "moonshot");

  now += 31_000;
  assert.equal(registry.selectProvider("auto"), "openai");
});

test("Moonshot report preserves Kimi chat-completions metadata", () => {
  const registry = new ProviderHealthRegistry({
    env: {
      MOONSHOT_API_KEY: "configured"
    },
    now: () => 1_000
  });

  const moonshot = registry.report().providers.find((provider) => provider.id === "moonshot");

  assert.equal(moonshot.configured, true);
  assert.equal(moonshot.model, "kimi-k3");
  assert.equal(moonshot.endpoint, "https://api.moonshot.ai/v1/chat/completions");
  assert.equal(moonshot.apiStyle, "chat-completions");
  assert.equal(moonshot.supportsTools, true);
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
      OPENAI_MODEL: "gpt-5.6",
      MOONSHOT_API_KEY: secret,
      MOONSHOT_MODEL: "kimi-k3"
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
