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


test("Project Billing Hub combines card planning with read-only crypto status", () => {
  assert.match(page, /UNIFIED FUNDING BRIDGE/);
  assert.match(page, /CARD \+ CRYPTO/);
  assert.match(page, /\/api\/eagle-eyes\/crypto\/status/);
  assert.match(page, /Card → crypto connection: NOT CONNECTED/);
  assert.match(page, /No purchase, charge, transfer, signing, or broadcast was performed/);
});


test("Project Billing Hub exposes guarded Coinbase setup without importing credentials", () => {
  assert.match(page, /COINBASE ONRAMP SETUP/);
  assert.match(page, /USER CONFIRMED LINKED/);
  assert.match(page, /COINBASE ONRAMP/);
  assert.match(page, /Command Center never receives the card number, CVV, bank login, Coinbase password, or 2FA code/);
  assert.match(page, /AUTO PURCHASE/);
  assert.match(page, />OFF</);
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
