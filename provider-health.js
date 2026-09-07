"use strict";

const DEFAULT_COOLDOWN_MS = 30_000;

function nowIso(now = Date.now()) {
  return new Date(now).toISOString();
}

function configured(value) {
  return Boolean(String(value || "").trim());
}

class ProviderHealthRegistry {
  constructor({ env = process.env, cooldownMs = DEFAULT_COOLDOWN_MS, now = Date.now } = {}) {
    this.env = env;
    this.cooldownMs = Math.max(1000, Number(cooldownMs) || DEFAULT_COOLDOWN_MS);
    this.now = now;
    this.state = new Map();
  }

  definitions() {
    return [
      {
        id: "openai",
        label: "OpenAI",
        keyEnv: "OPENAI_API_KEY",
        modelEnv: "OPENAI_MODEL",
        defaultModel: "gpt-5.6",
        priority: 1
      },
      {
        id: "anthropic",
        label: "Anthropic Claude",
        keyEnv: "ANTHROPIC_API_KEY",
        modelEnv: "ANTHROPIC_MODEL",
        defaultModel: "",
        priority: 2
      }
    ];
  }

  recordSuccess(providerId) {
    const at = this.now();
    this.state.set(providerId, {
      status: "healthy",
      consecutiveFailures: 0,
      lastSuccessAt: at,
      lastFailureAt: null,
      cooldownUntil: null,
      lastError: null
    });
  }

  recordFailure(providerId, error) {
    const at = this.now();
    const previous = this.state.get(providerId) || {};
    const consecutiveFailures = (previous.consecutiveFailures || 0) + 1;

    this.state.set(providerId, {
      status: "degraded",
      consecutiveFailures,
      lastSuccessAt: previous.lastSuccessAt || null,
      lastFailureAt: at,
      cooldownUntil: at + this.cooldownMs,
      lastError: error instanceof Error ? error.message : String(error || "unknown failure")
    });
  }

  providerReport(definition) {
    const at = this.now();
    const runtime = this.state.get(definition.id) || {};
    const isConfigured = configured(this.env[definition.keyEnv]);
    const coolingDown = Number.isFinite(runtime.cooldownUntil) && runtime.cooldownUntil > at;

    let status = "unconfigured";
    if (isConfigured && coolingDown) status = "cooldown";
    else if (isConfigured && runtime.status) status = runtime.status;
    else if (isConfigured) status = "ready";

    return {
      id: definition.id,
      label: definition.label,
      configured: isConfigured,
      status,
      priority: definition.priority,
      model: String(this.env[definition.modelEnv] || definition.defaultModel || "").trim() || null,
      consecutiveFailures: runtime.consecutiveFailures || 0,
      lastSuccessAt: runtime.lastSuccessAt ? nowIso(runtime.lastSuccessAt) : null,
      lastFailureAt: runtime.lastFailureAt ? nowIso(runtime.lastFailureAt) : null,
      cooldownUntil: runtime.cooldownUntil ? nowIso(runtime.cooldownUntil) : null,
      lastError: runtime.lastError || null
    };
  }

  report() {
    const providers = this.definitions().map((definition) => this.providerReport(definition));
    const available = providers.filter((provider) =>
      provider.configured && !["cooldown", "unconfigured"].includes(provider.status)
    );

    return {
      ok: available.length > 0,
      mode: String(this.env.AI_PROVIDER || "auto").trim().toLowerCase() || "auto",
      availableProviders: available.map((provider) => provider.id),
      providers,
      timestamp: nowIso(this.now()),
      authority: "observation",
      commandEligible: false
    };
  }

  selectProvider(requested = "auto") {
    const mode = String(requested || "auto").trim().toLowerCase();
    const providers = this.report().providers;

    if (mode !== "auto") {
      const match = providers.find((provider) => provider.id === mode);
      return match && match.configured && match.status !== "cooldown" ? match.id : null;
    }

    return providers
      .filter((provider) => provider.configured && provider.status !== "cooldown")
      .sort((a, b) => a.priority - b.priority)[0]?.id || null;
  }
}

module.exports = {
  DEFAULT_COOLDOWN_MS,
  ProviderHealthRegistry
};
