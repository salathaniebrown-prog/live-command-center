"use strict";

const WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php";
const OPEN_METEO_GEOCODE = "https://geocoding-api.open-meteo.com/v1/search";
const OPEN_METEO_FORECAST = "https://api.open-meteo.com/v1/forecast";

function cleanText(value) {
  return String(value || "")
    .replace(/\s+/g, " ")
    .trim();
}

function clampLimit(value, fallback = 3, max = 5) {
  const n = Number(value);
  if (!Number.isFinite(n)) return fallback;
  return Math.max(1, Math.min(max, Math.trunc(n)));
}

async function fetchJson(url, timeoutMs = 10000) {
  const response = await fetch(url, {
    headers: {
      accept: "application/json",
      "user-agent": "EagleEyesWorldCommandOS/1.0"
    },
    signal: AbortSignal.timeout(timeoutMs)
  });

  if (!response.ok) {
    throw new Error(`Upstream returned HTTP ${response.status}`);
  }

  return response.json();
}

async function knowledgeSearch(query, limit = 3) {
  const q = cleanText(query);
  if (!q) {
    throw new Error("query is required");
  }

  const take = clampLimit(limit);
  const url =
    `${WIKIPEDIA_API}?action=query&generator=search` +
    `&gsrsearch=${encodeURIComponent(q)}` +
    `&gsrlimit=${take}` +
    "&prop=extracts%7Cinfo&inprop=url&exintro=1&explaintext=1&exsentences=4&format=json&utf8=1";

  const data = await fetchJson(url);
  const pages = Object.values(data?.query?.pages || {})
    .sort((a, b) => Number(a.index || 9999) - Number(b.index || 9999))
    .slice(0, take)
    .map((page) => ({
      title: cleanText(page.title),
      extract: cleanText(page.extract).slice(0, 1400),
      url:
        page.fullurl ||
        (page.title
          ? `https://en.wikipedia.org/wiki/${encodeURIComponent(String(page.title).replace(/ /g, "_"))}`
          : null)
    }));

  return {
    ok: true,
    query: q,
    source: "Wikipedia",
    simulated: false,
    count: pages.length,
    results: pages,
    timestamp: new Date().toISOString()
  };
}

function weatherCodeLabel(code) {
  const labels = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Rime fog",
    51: "Light drizzle",
    53: "Drizzle",
    55: "Heavy drizzle",
    56: "Light freezing drizzle",
    57: "Heavy freezing drizzle",
    61: "Light rain",
    63: "Rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Light snow",
    73: "Snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Light rain showers",
    81: "Rain showers",
    82: "Heavy rain showers",
    85: "Light snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with light hail",
    99: "Thunderstorm with heavy hail"
  };

  return labels[Number(code)] || `Weather code ${code}`;
}

async function globalWeather(location) {
  const place = cleanText(location);
  if (!place) {
    throw new Error("location is required");
  }

  const geocodeUrl =
    `${OPEN_METEO_GEOCODE}?name=${encodeURIComponent(place)}` +
    "&count=1&language=en&format=json";

  const geocode = await fetchJson(geocodeUrl);
  const hit = Array.isArray(geocode?.results) ? geocode.results[0] : null;

  if (!hit) {
    return {
      ok: false,
      location: place,
      source: "Open-Meteo",
      simulated: false,
      error: "Location not found",
      timestamp: new Date().toISOString()
    };
  }

  const forecastUrl =
    `${OPEN_METEO_FORECAST}?latitude=${encodeURIComponent(hit.latitude)}` +
    `&longitude=${encodeURIComponent(hit.longitude)}` +
    "&current=temperature_2m,apparent_temperature,precipitation,rain,weather_code,wind_speed_10m,wind_direction_10m" +
    "&temperature_unit=fahrenheit&wind_speed_unit=mph&precipitation_unit=inch&timezone=auto";

  const forecast = await fetchJson(forecastUrl);
  const current = forecast?.current || {};

  return {
    ok: true,
    source: "Open-Meteo",
    simulated: false,
    location: {
      name: hit.name || place,
      admin1: hit.admin1 || null,
      country: hit.country || null,
      countryCode: hit.country_code || null,
      latitude: hit.latitude,
      longitude: hit.longitude,
      timezone: forecast.timezone || hit.timezone || null
    },
    current: {
      time: current.time || null,
      temperatureF: Number.isFinite(current.temperature_2m)
        ? current.temperature_2m
        : null,
      feelsLikeF: Number.isFinite(current.apparent_temperature)
        ? current.apparent_temperature
        : null,
      precipitationIn: Number.isFinite(current.precipitation)
        ? current.precipitation
        : null,
      rainIn: Number.isFinite(current.rain) ? current.rain : null,
      weatherCode: Number.isFinite(current.weather_code)
        ? current.weather_code
        : null,
      conditions: Number.isFinite(current.weather_code)
        ? weatherCodeLabel(current.weather_code)
        : "Unavailable",
      windMph: Number.isFinite(current.wind_speed_10m)
        ? current.wind_speed_10m
        : null,
      windDirectionDeg: Number.isFinite(current.wind_direction_10m)
        ? current.wind_direction_10m
        : null
    },
    timestamp: new Date().toISOString()
  };
}

function formatKnowledge(data) {
  const lines = [
    "EAGLE EYES WORLD KNOWLEDGE",
    `Query: ${data.query}`,
    `Source: ${data.source}`,
    ""
  ];

  if (!data.results?.length) {
    lines.push("No matching encyclopedia result was found.");
  } else {
    data.results.forEach((item, index) => {
      lines.push(`${index + 1}. ${item.title}`);
      if (item.extract) {
        lines.push(`   ${item.extract}`);
      }
      if (item.url) {
        lines.push(`   ${item.url}`);
      }
    });
  }

  lines.push("", `Checked: ${data.timestamp}`);
  return lines.join("\n");
}

function formatWeather(data) {
  if (!data.ok) {
    return [
      "EAGLE EYES GLOBAL WEATHER",
      `Location: ${data.location}`,
      `Status: ${data.error || "Unavailable"}`,
      "No simulated data was substituted.",
      `Checked: ${data.timestamp}`
    ].join("\n");
  }

  const place = [
    data.location?.name,
    data.location?.admin1,
    data.location?.country
  ]
    .filter(Boolean)
    .join(", ");

  const c = data.current || {};

  return [
    "EAGLE EYES GLOBAL WEATHER",
    `Location: ${place || "N/A"}`,
    `Conditions: ${c.conditions || "N/A"}`,
    `Temperature: ${Number.isFinite(c.temperatureF) ? `${c.temperatureF}°F` : "N/A"}`,
    `Feels like: ${Number.isFinite(c.feelsLikeF) ? `${c.feelsLikeF}°F` : "N/A"}`,
    `Wind: ${Number.isFinite(c.windMph) ? `${c.windMph} mph` : "N/A"}`,
    `Timezone: ${data.location?.timezone || "N/A"}`,
    `Source: ${data.source}`,
    "Simulation: OFF",
    `Checked: ${data.timestamp}`
  ].join("\n");
}

function shouldUseFreeKnowledge(message, openAIConfigured) {
  const q = cleanText(message).toLowerCase();

  if (!q) {
    return false;
  }

  if (!openAIConfigured) {
    return true;
  }

  return /\b(?:who (?:is|was|are|were)|what (?:is|was|are|were)|where (?:is|was|are|were)|when (?:is|was|did)|tell me about|world knowledge|wikipedia|encyclopedia)\b/.test(q);
}

function worldOSStatus() {
  return {
    ok: true,
    name: "EAGLE EYES WORLD COMMAND OPERATING SYSTEM",
    version: "1.0",
    mode: "read-only intelligence",
    simulated: false,
    modules: [
      "Command Center health",
      "Live container metrics",
      "Railway deployment telemetry",
      "Executive mission brief",
      "NOAA/NWS alerts",
      "USGS earthquakes",
      "NASA EONET natural events",
      "Wikipedia world knowledge",
      "Open-Meteo global weather",
      "GPT-5.6 tool routing when API access is active"
    ],
    freeCapabilities: [
      "system health",
      "live metrics",
      "deployment state",
      "mission brief",
      "NWS alerts",
      "USGS earthquakes",
      "NASA EONET events",
      "encyclopedic knowledge lookup",
      "global current weather"
    ],
    timestamp: new Date().toISOString()
  };
}

module.exports = {
  knowledgeSearch,
  globalWeather,
  formatKnowledge,
  formatWeather,
  worldOSStatus,
  shouldUseFreeKnowledge
};
