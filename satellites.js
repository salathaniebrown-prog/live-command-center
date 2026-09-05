"use strict";

const fs = require("node:fs/promises");
const path = require("node:path");

const CELESTRAK_WEATHER_URL =
  "https://celestrak.org/NORAD/elements/gp.php?GROUP=WEATHER&FORMAT=JSON";
const MAX_SATELLITES = 30;
const CACHE_MS = 2 * 60 * 60 * 1000;

let elementCache = {
  records: null,
  fetchedAtMs: 0,
  fetchedAt: null
};

let satelliteLibraryPromise = null;

function limitValue(value) {
  return Math.max(
    1,
    Math.min(
      MAX_SATELLITES,
      Number(value) || MAX_SATELLITES
    )
  );
}

function validOmm(record) {
  return Boolean(
    record &&
      record.OBJECT_NAME &&
      record.NORAD_CAT_ID !== undefined &&
      record.EPOCH
  );
}

function resolveStatePath(value) {
  const candidate =
    value ||
    process.env.SATELLITE_STATE_PATH ||
    null;

  return candidate
    ? path.resolve(String(candidate))
    : null;
}

async function persistWeatherElements(
  statePath,
  records,
  fetchedAt
) {
  const target =
    resolveStatePath(statePath);

  if (!target) return false;

  await fs.mkdir(
    path.dirname(target),
    { recursive: true }
  );

  const temp =
    `${target}.${process.pid}.${Date.now()}.tmp`;

  const payload = {
    version: 1,
    source: "celestrak-weather",
    fetchedAt,
    records
  };

  await fs.writeFile(
    temp,
    JSON.stringify(payload),
    "utf8"
  );

  await fs.rename(temp, target);
  return true;
}

async function loadPersistedWeatherElements(
  statePath
) {
  const target =
    resolveStatePath(statePath);

  if (!target) return null;

  try {
    const raw =
      await fs.readFile(target, "utf8");
    const payload =
      JSON.parse(raw);
    const records =
      Array.isArray(payload.records)
        ? payload.records.filter(validOmm)
        : [];

    if (!records.length) return null;

    return {
      records,
      fetchedAt:
        typeof payload.fetchedAt === "string"
          ? payload.fetchedAt
          : null
    };
  } catch {
    return null;
  }
}

async function satelliteLibrary() {
  if (!satelliteLibraryPromise) {
    satelliteLibraryPromise =
      import("satellite.js");
  }

  return satelliteLibraryPromise;
}

async function fetchWeatherElements({
  fetchImpl = globalThis.fetch,
  nowMs = Date.now(),
  statePath = null
} = {}) {
  if (
    Array.isArray(elementCache.records) &&
    nowMs - elementCache.fetchedAtMs < CACHE_MS
  ) {
    return {
      records: elementCache.records,
      fetchedAt: elementCache.fetchedAt,
      cached: true,
      persistentFallback: false,
      persistentSaved: false
    };
  }

  let liveError = null;

  try {
    if (typeof fetchImpl !== "function") {
      throw new Error(
        "Fetch is unavailable for CelesTrak weather data"
      );
    }

    const response =
      await fetchImpl(
        CELESTRAK_WEATHER_URL,
        {
          headers: {
            accept: "application/json",
            "user-agent":
              "Eagle-Eyes-Live-Command-Center/1.0"
          },
          signal:
            AbortSignal.timeout(10000)
        }
      );

    if (!response.ok) {
      throw new Error(
        `CelesTrak returned HTTP ${response.status}`
      );
    }

    const data =
      await response.json();

    if (!Array.isArray(data)) {
      throw new Error(
        "CelesTrak weather response was not an array"
      );
    }

    const records =
      data.filter(validOmm);

    if (!records.length) {
      throw new Error(
        "CelesTrak returned no usable weather GP records"
      );
    }

    const fetchedAt =
      new Date(nowMs).toISOString();

    elementCache = {
      records,
      fetchedAtMs: nowMs,
      fetchedAt
    };

    let persistentSaved = false;

    try {
      persistentSaved =
        await persistWeatherElements(
          statePath,
          records,
          fetchedAt
        );
    } catch {
      persistentSaved = false;
    }

    return {
      records,
      fetchedAt,
      cached: false,
      persistentFallback: false,
      persistentSaved
    };
  } catch (error) {
    liveError = error;
  }

  const persisted =
    await loadPersistedWeatherElements(
      statePath
    );

  if (persisted) {
    elementCache = {
      records: persisted.records,
      fetchedAtMs: 0,
      fetchedAt: persisted.fetchedAt
    };

    return {
      records: persisted.records,
      fetchedAt: persisted.fetchedAt,
      cached: true,
      persistentFallback: true,
      persistentSaved: false,
      fallbackReason:
        liveError?.message ||
        "CelesTrak live fetch unavailable"
    };
  }

  throw liveError;
}

function projectOmm(
  omm,
  at,
  satellite
) {
  try {
    const satrec =
      satellite.json2satrec(
        omm
      );

    const propagated =
      satellite.propagate(
        satrec,
        at
      );

    if (
      !propagated ||
      !propagated.position ||
      typeof propagated.position === "boolean"
    ) {
      return null;
    }

    const gmst =
      satellite.gstime(at);

    const geodetic =
      satellite.eciToGeodetic(
        propagated.position,
        gmst
      );

    const latitude =
      satellite.degreesLat(
        geodetic.latitude
      );

    const longitude =
      satellite.degreesLong(
        geodetic.longitude
      );

    if (
      !Number.isFinite(latitude) ||
      !Number.isFinite(longitude)
    ) {
      return null;
    }

    return {
      name:
        String(
          omm.OBJECT_NAME
        ),
      noradId:
        String(
          omm.NORAD_CAT_ID
        ),
      objectId:
        omm.OBJECT_ID ||
        null,
      epoch:
        omm.EPOCH ||
        null,
      latitude:
        Number(
          latitude.toFixed(5)
        ),
      longitude:
        Number(
          longitude.toFixed(5)
        ),
      altitudeKm:
        Number.isFinite(
          geodetic.height
        )
          ? Number(
              geodetic.height.toFixed(2)
            )
          : null
    };
  } catch {
    return null;
  }
}

async function projectWeatherOmms(
  records,
  limit = MAX_SATELLITES,
  at = new Date(),
  satelliteImpl = null
) {
  const satellite =
    satelliteImpl ||
    await satelliteLibrary();

  return (records || [])
    .filter(validOmm)
    .slice(
      0,
      limitValue(limit)
    )
    .map(
      (record) =>
        projectOmm(
          record,
          at,
          satellite
        )
    )
    .filter(Boolean);
}

async function weatherSatellites(
  limit = MAX_SATELLITES,
  at = new Date(),
  options = {}
) {
  const requested =
    limitValue(limit);

  const source =
    await fetchWeatherElements(
      options
    );

  const satellites =
    await projectWeatherOmms(
      source.records,
      requested,
      at,
      options.satelliteImpl ||
        null
    );

  if (!satellites.length) {
    throw new Error(
      "No current satellite positions could be propagated"
    );
  }

  return {
    ok: true,
    source: "celestrak",
    sourceUrl:
      CELESTRAK_WEATHER_URL,
    group: "weather",
    simulated: false,
    requested,
    count:
      satellites.length,
    cacheMaxAgeSeconds:
      Math.floor(
        CACHE_MS / 1000
      ),
    upstreamFetchedAt:
      source.fetchedAt,
    upstreamCached:
      source.cached,
    persistentFallback:
      Boolean(source.persistentFallback),
    fallbackReason:
      source.fallbackReason || null,
    positionsAt:
      at.toISOString(),
    satellites,
    timestamp:
      new Date().toISOString()
  };
}

function resetCache() {
  elementCache = {
    records: null,
    fetchedAtMs: 0,
    fetchedAt: null
  };
}

module.exports = {
  CELESTRAK_WEATHER_URL,
  MAX_SATELLITES,
  CACHE_MS,
  fetchWeatherElements,
  projectOmm,
  projectWeatherOmms,
  weatherSatellites,
  resetCache
};
