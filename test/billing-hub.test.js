"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const billingPath = path.join(__dirname, "..", "public", "billing.html");
const page = fs.readFileSync(billingPath, "utf8");

test("Project Billing Hub exposes the expected career services", () => {
  for (const label of [
    "PROJECT BILLING HUB",
    "Railway",
    "ChatGPT",
    "OpenAI API",
    "Google AI Studio / Gemini",
    "GitHub",
    "Cloudflare",
    "Expo / EAS",
    "Figma",
    "Runway",
    "Magnific"
  ]) {
    assert.equal(page.includes(label), true, label);
  }
});

test("Project Billing Hub defaults to the approved $100 monthly ceiling", () => {
  assert.match(page, /monthlyCap:100/);
  assert.match(page, /id="capDisplay">\$100\.00/);
});

test("Project Billing Hub does not collect sensitive payment or wallet credentials", () => {
  for (const forbidden of [
    'id="cardNumber"',
    'id="cvv"',
    'id="expiration"',
    'id="bankLogin"',
    'id="privateKey"',
    'id="seedPhrase"',
    'type="password"'
  ]) {
    assert.equal(page.includes(forbidden), false, forbidden);
  }
  assert.match(page, /NO CARD NUMBERS/);
  assert.match(page, /localStorage/);
});

test("Project Billing Hub runtime checks remain read-only", () => {
  assert.match(page, /getj\('\/api\/health'\)/);
  assert.match(page, /getj\('\/api\/deployment'\)/);
  assert.equal(page.includes("method:'POST'"), false);
  assert.equal(page.includes('method:"POST"'), false);
  assert.match(page, /Billing plan\/credits\/card status: NOT INFERRED/);
});
