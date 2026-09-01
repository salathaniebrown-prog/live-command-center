"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { shouldUseFreeKnowledge } = require("../world-os");

test("routes the World Knowledge quick command to the free source when OpenAI is configured", () => {
  assert.equal(
    shouldUseFreeKnowledge("Who is Katherine Johnson?", true),
    true
  );
});

test("preserves GPT routing for unmatched prompts when OpenAI is configured", () => {
  assert.equal(
    shouldUseFreeKnowledge("Analyze these priorities", true),
    false
  );
});

test("uses free knowledge mode for unmatched prompts when OpenAI is unavailable", () => {
  assert.equal(
    shouldUseFreeKnowledge("Katherine Johnson", false),
    true
  );
});
