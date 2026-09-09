"use strict";

const crypto = require("crypto");

const ADS_ENDPOINT = "https://bzr.openai.com/v1/events";
const INTEGRATION_SOURCE = "eagle_eyes_live_command_center";

function enabledFromEnv(env = process.env) {
  return String(env.OPENAI_ADS_MEASUREMENT_ENABLED || "").toLowerCase() === "true";
}

function getConfig(env = process.env) {
  return {
    enabled: enabledFromEnv(env),
    pixelId: String(env.OPENAI_ADS_PIXEL_ID || "").trim(),
    capiKey: String(env.OPENAI_ADS_CAPI_KEY || "").trim(),
    siteOrigin: String(env.OPENAI_ADS_SITE_ORIGIN || "").trim(),
    validateOnly:
      String(env.OPENAI_ADS_VALIDATE_ONLY || "").toLowerCase() === "true"
  };
}

function browserConfig(env = process.env) {
  const config = getConfig(env);
  return {
    enabled: Boolean(config.enabled && config.pixelId),
    pixelId: config.enabled ? config.pixelId : ""
  };
}

function sha256(value) {
  return crypto
    .createHash("sha256")
    .update(String(value || ""), "utf8")
    .digest("hex");
}

function getOpaqueCookie(req, name) {
  const header = String(req.get("cookie") || "");
  const prefix = `${name}=`;

  for (const part of header.split(";")) {
    const item = part.trimStart();
    if (item.startsWith(prefix)) return item.slice(prefix.length);
  }

  return "";
}

function parseHttpOrigin(value) {
  if (!value) return null;

  try {
    const url = new URL(value);
    if (url.protocol !== "https:" && url.protocol !== "http:") return null;
    return url.origin;
  } catch {
    return null;
  }
}

function requestOrigin(req) {
  const originHeader = parseHttpOrigin(req.get("origin"));
  const host = String(req.get("host") || "").toLowerCase();

  if (originHeader) {
    try {
      if (new URL(originHeader).host.toLowerCase() === host) return originHeader;
    } catch {
      // Continue to the proxy-derived fallback below.
    }
  }

  if (!host) return null;
  const forwardedProto = String(req.get("x-forwarded-proto") || "")
    .split(",")[0]
    .trim()
    .toLowerCase();
  const protocol = forwardedProto === "https" ? "https" : req.protocol === "https" ? "https" : "http";
  return `${protocol}://${host}`;
}

function sanitizeSourceUrl(req, candidate, env = process.env) {
  const config = getConfig(env);
  const canonicalOrigin = parseHttpOrigin(config.siteOrigin);
  const currentOrigin = requestOrigin(req);
  const allowedOrigins = new Set([canonicalOrigin, currentOrigin].filter(Boolean));

  if (candidate) {
    try {
      const url = new URL(String(candidate));
      if (
        (url.protocol === "https:" || url.protocol === "http:") &&
        allowedOrigins.has(url.origin)
      ) {
        return `${url.origin}${url.pathname || "/"}`;
      }
    } catch {
      // Use a trusted fallback below.
    }
  }

  const fallbackOrigin = canonicalOrigin || currentOrigin;
  return fallbackOrigin ? `${fallbackOrigin}/request-deployment.html` : "";
}

function buildLeadCreatedEvent({ req, leadId, email, sourceUrl, env = process.env, now = Date.now }) {
  const cleanSourceUrl = sanitizeSourceUrl(req, sourceUrl, env);
  if (!cleanSourceUrl) return null;

  const event = {
    id: String(leadId),
    type: "lead_created",
    timestamp_ms: now(),
    source_url: cleanSourceUrl,
    action_source: "web",
    user: {
      emails_sha256: [sha256(String(email || "").trim().toLowerCase())],
      user_agent: String(req.get("user-agent") || "").slice(0, 1024)
    },
    data: {
      type: "customer_action"
    }
  };

  const oppref = getOpaqueCookie(req, "__oppref");
  if (oppref) event.oppref = oppref;

  return event;
}

async function sendLeadCreated({ req, leadId, email, sourceUrl, env = process.env, fetchImpl = fetch }) {
  const config = getConfig(env);

  if (!config.enabled) return { sent: false, reason: "disabled" };
  if (!config.pixelId) return { sent: false, reason: "pixel_id_missing" };
  if (!config.capiKey) return { sent: false, reason: "capi_key_missing" };

  const event = buildLeadCreatedEvent({ req, leadId, email, sourceUrl, env });
  if (!event) return { sent: false, reason: "source_url_unavailable" };

  const response = await fetchImpl(
    `${ADS_ENDPOINT}?pid=${encodeURIComponent(config.pixelId)}`,
    {
      method: "POST",
      headers: {
        authorization: `Bearer ${config.capiKey}`,
        "content-type": "application/json"
      },
      body: JSON.stringify({
        validate_only: config.validateOnly,
        integration_source: INTEGRATION_SOURCE,
        events: [event]
      }),
      signal: AbortSignal.timeout(1500)
    }
  );

  if (!response.ok) {
    const error = new Error(`OpenAI Ads CAPI returned HTTP ${response.status}`);
    error.status = response.status;
    throw error;
  }

  return { sent: true, eventId: event.id };
}

function queueLeadCreated(args) {
  Promise.resolve()
    .then(() => sendLeadCreated(args))
    .then((result) => {
      if (result.sent) {
        console.log(
          JSON.stringify({
            event: "openai_ads_conversion_sent",
            type: "lead_created",
            eventId: result.eventId
          })
        );
      }
    })
    .catch((error) => {
      console.error(
        "openai ads conversion delivery failed",
        error && error.status ? `HTTP ${error.status}` : error?.name || "Error"
      );
    });
}

module.exports = {
  ADS_ENDPOINT,
  INTEGRATION_SOURCE,
  browserConfig,
  buildLeadCreatedEvent,
  getConfig,
  getOpaqueCookie,
  queueLeadCreated,
  sanitizeSourceUrl,
  sendLeadCreated,
  sha256
};
