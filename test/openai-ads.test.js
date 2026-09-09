"use strict";

const assert = require("node:assert/strict");
const test = require("node:test");
const {
  browserConfig,
  buildLeadCreatedEvent,
  sanitizeSourceUrl,
  sendLeadCreated,
  sha256
} = require("../openai-ads");

function fakeRequest(headers = {}, protocol = "https") {
  const normalized = Object.fromEntries(
    Object.entries(headers).map(([key, value]) => [key.toLowerCase(), value])
  );

  return {
    protocol,
    get(name) {
      return normalized[String(name).toLowerCase()] || "";
    }
  };
}

test("browser config exposes only the public pixel identifier", () => {
  const config = browserConfig({
    OPENAI_ADS_MEASUREMENT_ENABLED: "true",
    OPENAI_ADS_PIXEL_ID: "pixel_test",
    OPENAI_ADS_CAPI_KEY: "placeholder"
  });

  assert.deepEqual(config, {
    enabled: true,
    pixelId: "pixel_test"
  });
  assert.equal("capiKey" in config, false);
});

test("browser config stays disabled without explicit measurement enablement", () => {
  assert.deepEqual(
    browserConfig({ OPENAI_ADS_PIXEL_ID: "pixel_test" }),
    { enabled: false, pixelId: "" }
  );
});

test("source URL accepts trusted browser context and strips query and fragment", () => {
  const req = fakeRequest({
    host: "example.test",
    origin: "https://example.test"
  });

  assert.equal(
    sanitizeSourceUrl(
      req,
      "https://example.test/request-deployment.html?oppref=opaque#form",
      {}
    ),
    "https://example.test/request-deployment.html"
  );
});

test("lead event preserves opaque attribution cookies and hashes normalized email", () => {
  const req = fakeRequest({
    host: "example.test",
    origin: "https://example.test",
    cookie: "__oppref=opaque%2Bvalue; __obref=browser-ref%2Fraw; session=ignored",
    "user-agent": "EagleEyesTest/1.0"
  });

  const event = buildLeadCreatedEvent({
    req,
    leadId: "lead_123",
    email: "  USER@Example.COM ",
    sourceUrl: "https://example.test/request-deployment.html?x=1#y",
    env: {},
    now: () => 1770000000000
  });

  assert.equal(event.id, "lead_123");
  assert.equal(event.type, "lead_created");
  assert.equal(event.action_source, "web");
  assert.equal(event.timestamp_ms, 1770000000000);
  assert.equal(event.oppref, "opaque%2Bvalue");
  assert.equal(event.user.obref, "browser-ref%2Fraw");
  assert.equal(event.source_url, "https://example.test/request-deployment.html");
  assert.deepEqual(event.data, { type: "customer_action" });
  assert.deepEqual(event.user.emails_sha256, [sha256("user@example.com")]);
  assert.equal(event.user.user_agent, "EagleEyesTest/1.0");
});

test("CAPI dispatch uses server-only authorization and documented event payload", async () => {
  const req = fakeRequest({
    host: "example.test",
    origin: "https://example.test",
    "user-agent": "EagleEyesTest/1.0"
  });
  const calls = [];
  const fetchImpl = async (url, options) => {
    calls.push({ url, options });
    return { ok: true, status: 200 };
  };

  const result = await sendLeadCreated({
    req,
    leadId: "lead_456",
    email: "person@example.com",
    sourceUrl: "https://example.test/request-deployment.html",
    env: {
      OPENAI_ADS_MEASUREMENT_ENABLED: "true",
      OPENAI_ADS_PIXEL_ID: "pixel_test",
      OPENAI_ADS_CAPI_KEY: "placeholder",
      OPENAI_ADS_SITE_ORIGIN: "https://example.test",
      OPENAI_ADS_VALIDATE_ONLY: "true"
    },
    fetchImpl
  });

  assert.deepEqual(result, { sent: true, eventId: "lead_456" });
  assert.equal(calls.length, 1);
  assert.equal(calls[0].url, "https://bzr.openai.com/v1/events?pid=pixel_test");
  assert.equal(calls[0].options.headers.authorization, "Bearer placeholder");

  const body = JSON.parse(calls[0].options.body);
  assert.equal(body.validate_only, true);
  assert.equal(body.integration_source, "eagle_eyes_live_command_center");
  assert.equal(body.events[0].id, "lead_456");
  assert.equal(body.events[0].type, "lead_created");
  assert.equal(body.events[0].data.type, "customer_action");
  assert.equal(calls[0].options.body.includes("placeholder"), false);
});

test("disabled measurement never calls the network", async () => {
  let called = false;
  const result = await sendLeadCreated({
    req: fakeRequest({ host: "example.test" }),
    leadId: "lead_disabled",
    email: "person@example.com",
    sourceUrl: "https://example.test/request-deployment.html",
    env: {},
    fetchImpl: async () => {
      called = true;
      return { ok: true, status: 200 };
    }
  });

  assert.deepEqual(result, { sent: false, reason: "disabled" });
  assert.equal(called, false);
});
