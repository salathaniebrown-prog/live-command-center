"use strict";

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

async function satelliteLibrary() {
  if (!satelliteLibraryPromise) {
    satelliteLibraryPromise =
      import("satellite.js");
  }

  return satelliteLibraryPromise;
}

async function fetchWeatherElements({
  fetchImpl = globalThis.fetch,
  nowMs = Date.now()
} = {}) {
  if (
    Array.isArray(elementCache.records) &&
    nowMs - elementCache.fetchedAtMs < CACHE_MS
  ) {
    return {
      records: elementCache.records,
      fetchedAt: elementCache.fetchedAt,
      cached: true
    };
  }

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

  return {
    records,
    fetchedAt,
    cached: false
  };
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
