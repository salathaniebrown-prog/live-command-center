"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const { shouldUseFreeKnowledge, globalWeather } = require("../world-os");

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


test("globalWeather requests inch precipitation units before labeling rainfall as inches", async (t) => {
  const originalFetch = global.fetch;
  const requested = [];

  t.after(() => {
    global.fetch = originalFetch;
  });

  global.fetch = async (url) => {
    requested.push(String(url));

    if (String(url).includes("geocoding-api.open-meteo.com")) {
      return {
        ok: true,
        async json() {
          return {
            results: [{
              name: "Raleigh",
              admin1: "North Carolina",
              country: "United States",
              country_code: "US",
              latitude: 35.7796,
              longitude: -78.6382,
              timezone: "America/New_York"
            }]
          };
        }
      };
    }

    return {
      ok: true,
      async json() {
        return {
          timezone: "America/New_York",
          current: {
            time: "2026-09-01T19:00",
            temperature_2m: 80,
            apparent_temperature: 82,
            precipitation: 0.25,
            rain: 0.25,
            weather_code: 61,
            wind_speed_10m: 8,
            wind_direction_10m: 180
          }
        };
      }
    };
  };

  const result = await globalWeather("Raleigh");

  assert.equal(result.ok, true);
  assert.equal(result.current.precipitationIn, 0.25);
  assert.equal(result.current.rainIn, 0.25);

  const forecastUrl = requested.find((url) =>
    url.includes("api.open-meteo.com/v1/forecast")
  );

  assert.ok(forecastUrl);
  assert.match(forecastUrl, /precipitation_unit=inch/);
  assert.match(forecastUrl, /temperature_unit=fahrenheit/);
  assert.match(forecastUrl, /wind_speed_unit=mph/);
});
