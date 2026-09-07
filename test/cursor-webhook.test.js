"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const {
  CursorWebhookStore,
  expectedSignature,
  verifyCursorWebhook,
  parseCursorWebhook
} = require("../cursor-webhook");

const SECRET = "cursor-webhook-test-secret";

function payload(overrides = {}) {
  return {
    event: "statusChange",
    timestamp: "2026-09-07T19:00:00Z",
    id: "bc_abc123",
    status: "FINISHED",
    source: {
      repository: "https://github.com/example/repo",
      ref: "main"
    },
    target: {
      url: "https://cursor.com/agents?id=bc_abc123",
      branchName: "cursor/demo-1234",
      prUrl: "https://github.com/example/repo/pull/12"
    },
    summary: "Completed demo update",
    ...overrides
  };
}

function raw(overrides) {
  return Buffer.from(JSON.stringify(payload(overrides)), "utf8");
}

test("valid Cursor webhook signature is accepted from the exact raw body", () => {
  const body = raw();
  const signature = expectedSignature(SECRET, body);

  assert.equal(verifyCursorWebhook(SECRET, body, signature), true);
  assert.equal(
    verifyCursorWebhook(
      SECRET,
      Buffer.from(body.toString("utf8") + " ", "utf8"),
      signature
    ),
    false
  );
});

test("Cursor statusChange payload is normalized without storing raw payload", () => {
  const parsed = parseCursorWebhook(raw());

  assert.equal(parsed.event, "statusChange");
  assert.equal(parsed.id, "bc_abc123");
  assert.equal(parsed.status, "FINISHED");
  assert.equal(parsed.source.ref, "main");
  assert.equal(parsed.target.branchName, "cursor/demo-1234");
});

test("store accepts signed FINISHED event and deduplicates delivery IDs", () => {
  const store = new CursorWebhookStore();
  const body = raw();
  const signature = expectedSignature(SECRET, body);
  const request = {
    rawBody: body,
    signature,
    deliveryId: "delivery-1",
    eventType: "statusChange",
    secret: SECRET
  };

  const first = store.accept(request);
  const second = store.accept(request);
  const status = store.status({ configured: true });

  assert.equal(first.accepted, true);
  assert.equal(first.duplicate, false);
  assert.equal(first.event.status, "FINISHED");
  assert.equal(second.duplicate, true);
  assert.equal(status.recentCount, 1);
  assert.equal(status.latest.deliveryId, "delivery-1");
  assert.equal(status.rawPayloadStored, false);
});

test("store accepts ERROR events", () => {
  const store = new CursorWebhookStore();
  const body = raw({ status: "ERROR", summary: "Agent failed" });

  const result = store.accept({
    rawBody: body,
    signature: expectedSignature(SECRET, body),
    deliveryId: "delivery-error",
    eventType: "statusChange",
    secret: SECRET
  });

  assert.equal(result.event.status, "ERROR");
});

test("invalid signature fails closed", () => {
  const store = new CursorWebhookStore();
  const body = raw();

  assert.throws(
    () =>
      store.accept({
        rawBody: body,
        signature: "sha256=" + "0".repeat(64),
        deliveryId: "delivery-2",
        eventType: "statusChange",
        secret: SECRET
      }),
    (error) =>
      error.statusCode === 401 &&
      error.code === "INVALID_SIGNATURE"
  );
});

test("missing webhook secret fails closed", () => {
  const store = new CursorWebhookStore();
  const body = raw();

  assert.throws(
    () =>
      store.accept({
        rawBody: body,
        signature: expectedSignature(SECRET, body),
        deliveryId: "delivery-3",
        eventType: "statusChange",
        secret: ""
      }),
    (error) =>
      error.statusCode === 503 &&
      error.code === "WEBHOOK_SECRET_NOT_CONFIGURED"
  );
});

test("unsupported event header or status is rejected", () => {
  const store = new CursorWebhookStore();
  const body = raw();

  assert.throws(
    () =>
      store.accept({
        rawBody: body,
        signature: expectedSignature(SECRET, body),
        deliveryId: "delivery-4",
        eventType: "otherEvent",
        secret: SECRET
      }),
    /statusChange/
  );

  const unsupportedBody = raw({ status: "RUNNING" });

  assert.throws(
    () =>
      store.accept({
        rawBody: unsupportedBody,
        signature: expectedSignature(SECRET, unsupportedBody),
        deliveryId: "delivery-5",
        eventType: "statusChange",
        secret: SECRET
      }),
    /Unsupported Cursor statusChange status/
  );
});
