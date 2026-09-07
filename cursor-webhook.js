"use strict";

const crypto = require("crypto");

const MAX_RECENT_EVENTS = 50;
const MAX_DELIVERY_IDS = 500;
const SUPPORTED_EVENT = "statusChange";
const SUPPORTED_STATUSES = new Set(["ERROR", "FINISHED"]);

class CursorWebhookError extends Error {
  constructor(message, statusCode, code) {
    super(message);
    this.name = "CursorWebhookError";
    this.statusCode = statusCode;
    this.code = code;
  }
}

function rawBuffer(value) {
  if (Buffer.isBuffer(value)) {
    return value;
  }

  if (typeof value === "string") {
    return Buffer.from(value, "utf8");
  }

  throw new CursorWebhookError(
    "Cursor webhook raw request body is required",
    400,
    "RAW_BODY_REQUIRED"
  );
}

function expectedSignature(secret, rawBody) {
  return (
    "sha256=" +
    crypto
      .createHmac("sha256", String(secret || ""))
      .update(rawBuffer(rawBody))
      .digest("hex")
  );
}

function verifyCursorWebhook(secret, rawBody, signature) {
  if (!secret) {
    throw new CursorWebhookError(
      "Cursor webhook is locked until CURSOR_WEBHOOK_SECRET is configured",
      503,
      "WEBHOOK_SECRET_NOT_CONFIGURED"
    );
  }

  const received = String(signature || "").trim().toLowerCase();

  if (!/^sha256=[0-9a-f]{64}$/.test(received)) {
    return false;
  }

  const expected = expectedSignature(secret, rawBody).toLowerCase();
  const receivedBuffer = Buffer.from(received, "utf8");
  const expectedBuffer = Buffer.from(expected, "utf8");

  return (
    receivedBuffer.length === expectedBuffer.length &&
    crypto.timingSafeEqual(receivedBuffer, expectedBuffer)
  );
}

function cleanString(value, maxLength = 2048) {
  if (typeof value !== "string") {
    return null;
  }

  const text = value.trim();
  return text ? text.slice(0, maxLength) : null;
}

function parseCursorWebhook(rawBody) {
  const raw = rawBuffer(rawBody);
  let payload;

  try {
    payload = JSON.parse(raw.toString("utf8"));
  } catch {
    throw new CursorWebhookError(
      "Cursor webhook body must be valid JSON",
      400,
      "INVALID_JSON"
    );
  }

  if (!payload || typeof payload !== "object" || Array.isArray(payload)) {
    throw new CursorWebhookError(
      "Cursor webhook body must be a JSON object",
      400,
      "INVALID_PAYLOAD"
    );
  }

  if (payload.event !== SUPPORTED_EVENT) {
    throw new CursorWebhookError(
      "Unsupported Cursor webhook event",
      400,
      "UNSUPPORTED_EVENT"
    );
  }

  const status = cleanString(payload.status, 32)?.toUpperCase();

  if (!status || !SUPPORTED_STATUSES.has(status)) {
    throw new CursorWebhookError(
      "Unsupported Cursor statusChange status",
      400,
      "UNSUPPORTED_STATUS"
    );
  }

  const agentId = cleanString(payload.id, 256);

  if (!agentId) {
    throw new CursorWebhookError(
      "Cursor webhook id is required",
      400,
      "AGENT_ID_REQUIRED"
    );
  }

  return {
    event: SUPPORTED_EVENT,
    timestamp: cleanString(payload.timestamp, 128),
    id: agentId,
    status,
    source: {
      repository: cleanString(payload.source?.repository),
      ref: cleanString(payload.source?.ref, 512)
    },
    target: {
      url: cleanString(payload.target?.url),
      branchName: cleanString(payload.target?.branchName, 512),
      prUrl: cleanString(payload.target?.prUrl)
    },
    summary: cleanString(payload.summary, 4000)
  };
}

class CursorWebhookStore {
  constructor() {
    this.recentEvents = [];
    this.deliveryIds = new Set();
  }

  accept({ rawBody, signature, deliveryId, eventType, secret } = {}) {
    const normalizedDeliveryId = cleanString(deliveryId, 256);
    const normalizedEventType = cleanString(eventType, 128);

    if (!normalizedDeliveryId) {
      throw new CursorWebhookError(
        "X-Webhook-ID is required",
        400,
        "DELIVERY_ID_REQUIRED"
      );
    }

    if (normalizedEventType !== SUPPORTED_EVENT) {
      throw new CursorWebhookError(
        "X-Webhook-Event must be statusChange",
        400,
        "INVALID_EVENT_HEADER"
      );
    }

    if (!verifyCursorWebhook(secret, rawBody, signature)) {
      throw new CursorWebhookError(
        "Invalid Cursor webhook signature",
        401,
        "INVALID_SIGNATURE"
      );
    }

    if (this.deliveryIds.has(normalizedDeliveryId)) {
      return {
        ok: true,
        accepted: true,
        duplicate: true,
        deliveryId: normalizedDeliveryId
      };
    }

    const event = parseCursorWebhook(rawBody);
    const receivedAt = new Date().toISOString();
    const storedEvent = {
      deliveryId: normalizedDeliveryId,
      receivedAt,
      ...event
    };

    this.deliveryIds.add(normalizedDeliveryId);
    this.recentEvents.unshift(storedEvent);

    if (this.recentEvents.length > MAX_RECENT_EVENTS) {
      this.recentEvents.length = MAX_RECENT_EVENTS;
    }

    while (this.deliveryIds.size > MAX_DELIVERY_IDS) {
      const oldest = this.deliveryIds.values().next().value;
      this.deliveryIds.delete(oldest);
    }

    return {
      ok: true,
      accepted: true,
      duplicate: false,
      deliveryId: normalizedDeliveryId,
      event: storedEvent
    };
  }

  status({ configured = false } = {}) {
    return {
      ok: true,
      configured: Boolean(configured),
      endpoint: "/api/webhooks/cursor",
      supportedEvent: SUPPORTED_EVENT,
      supportedStatuses: [...SUPPORTED_STATUSES],
      recentCount: this.recentEvents.length,
      latest: this.recentEvents[0] || null,
      recent: this.recentEvents.slice(0, 20),
      persistence: "memory-only",
      rawPayloadStored: false,
      timestamp: new Date().toISOString()
    };
  }
}

module.exports = {
  MAX_RECENT_EVENTS,
  SUPPORTED_EVENT,
  SUPPORTED_STATUSES,
  CursorWebhookError,
  CursorWebhookStore,
  expectedSignature,
  verifyCursorWebhook,
  parseCursorWebhook
};
