"use strict";

(() => {
  let readyPromise = null;

  function loadPixelSdk() {
    if (window.oaiq) return;

    const queue = function () {
      queue.q.push(arguments);
    };
    queue.q = [];
    window.oaiq = queue;

    const script = document.createElement("script");
    script.async = true;
    script.src = "https://bzrcdn.openai.com/sdk/oaiq.min.js";
    const firstScript = document.getElementsByTagName("script")[0];
    firstScript.parentNode.insertBefore(script, firstScript);
  }

  async function getConfig() {
    const response = await fetch("/api/openai-ads/config", {
      credentials: "same-origin",
      headers: { accept: "application/json" }
    });
    if (!response.ok) return null;
    return response.json();
  }

  async function ensureReady() {
    if (!readyPromise) {
      readyPromise = getConfig()
        .then((config) => {
          if (!config?.enabled || !config.pixelId) return null;
          loadPixelSdk();
          window.oaiq("init", { pixelId: config.pixelId });
          return config;
        })
        .catch(() => null);
    }

    return readyPromise;
  }

  async function hashEmail(email) {
    const normalized = String(email || "").trim().toLowerCase();
    if (!normalized || !window.crypto?.subtle) return "";

    const bytes = new TextEncoder().encode(normalized);
    const digest = await window.crypto.subtle.digest("SHA-256", bytes);
    return Array.from(new Uint8Array(digest))
      .map((byte) => byte.toString(16).padStart(2, "0"))
      .join("");
  }

  async function measureLead({ eventId, email }) {
    try {
      const config = await ensureReady();
      if (!config || !eventId) return false;

      const emailHash = await hashEmail(email);
      if (emailHash) {
        window.oaiq("init", {
          user: { email_sha256: emailHash }
        });
      }

      window.oaiq(
        "measure",
        "lead_created",
        { type: "customer_action" },
        { event_id: String(eventId) }
      );
      return true;
    } catch {
      return false;
    }
  }

  window.EagleEyesOpenAIAds = Object.freeze({
    ensureReady,
    measureLead
  });

  void ensureReady();
})();
