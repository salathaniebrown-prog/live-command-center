"use strict";

const SCHEMA_VERSION = "eagle-eyes.data-spine.v1";

function finite(value) {
  return Number.isFinite(value) ? value : null;
}

function isoFromMs(value) {
  return Number.isFinite(value)
    ? new Date(value).toISOString()
    : null;
}

function pointFromGeometry(geometry, depthUnit = null) {
  if (
    !geometry ||
    geometry.type !== "Point" ||
    !Array.isArray(geometry.coordinates)
  ) {
    return null;
  }

  const [longitude, latitude, depth] = geometry.coordinates;

  if (!Number.isFinite(longitude) || !Number.isFinite(latitude)) {
    return null;
  }

  return {
    latitude,
    longitude,
    depth: Number.isFinite(depth) ? depth : null,
    depthUnit
  };
}

function spineRecord({
  source,
  sourceId,
  eventType,
  title,
  severity = null,
  magnitude = null,
  geometry = null,
  position = null,
  occurredAt = null,
  updatedAt = null,
  expiresAt = null,
  sourceUrl = null,
  retrievedAt,
  sourceMetadata = null
}) {
  return {
    schemaVersion: SCHEMA_VERSION,
    source,
    sourceId: sourceId || null,
    eventType: eventType || null,
    title: title || null,
    severity: severity || null,
    magnitude: Number.isFinite(magnitude) ? magnitude : null,
    geometry: geometry || null,
    position: position || null,
    occurredAt: occurredAt || null,
    updatedAt: updatedAt || null,
    expiresAt: expiresAt || null,
    sourceUrl: sourceUrl || null,
    retrievedAt,
    sourceMetadata: sourceMetadata || null
  };
}

function normalizeUsgs(data, sourceUrl, limit = 10, retrievedAt = new Date().toISOString()) {
  const events = (data?.features || [])
    .slice(0, limit)
    .map((feature) => {
      const p = feature?.properties || {};
      const geometry = feature?.geometry || null;
      const position = pointFromGeometry(geometry, "km");
      const time = isoFromMs(p.time);
      const updatedAt = isoFromMs(p.updated);
      const sourceId = feature?.id || null;
      const title = p.title || null;
      const magnitude = finite(p.mag);
      const url = p.url || null;

      return {
        id: sourceId,
        title,
        magnitude,
        place: p.place || null,
        time,
        url,
        updatedAt,
        coordinates: position
          ? {
              latitude: position.latitude,
              longitude: position.longitude,
              depthKm: position.depth
            }
          : null,
        spine: spineRecord({
          source: "usgs",
          sourceId,
          eventType: p.type || "earthquake",
          title,
          severity: p.alert || null,
          magnitude,
          geometry,
          position,
          occurredAt: time,
          updatedAt,
          sourceUrl: url,
          retrievedAt,
          sourceMetadata: {
            status: p.status || null,
            tsunami: Number.isFinite(p.tsunami) ? p.tsunami : null,
            significance: finite(p.sig),
            feltReports: finite(p.felt),
            detailUrl: p.detail || null
          }
        }),
        sourceRecord: {
          id: sourceId,
          type: feature?.type || null,
          properties: {
            mag: magnitude,
            place: p.place || null,
            time: p.time ?? null,
            updated: p.updated ?? null,
            tz: p.tz ?? null,
            url,
            detail: p.detail || null,
            felt: p.felt ?? null,
            cdi: p.cdi ?? null,
            mmi: p.mmi ?? null,
            alert: p.alert || null,
            status: p.status || null,
            tsunami: p.tsunami ?? null,
            sig: p.sig ?? null,
            net: p.net || null,
            code: p.code || null,
            ids: p.ids || null,
            sources: p.sources || null,
            types: p.types || null,
            nst: p.nst ?? null,
            dmin: p.dmin ?? null,
            rms: p.rms ?? null,
            gap: p.gap ?? null,
            magType: p.magType || null,
            type: p.type || null,
            title
          }
        }
      };
    });

  return {
    ok: true,
    source: "usgs",
    sourceUrl,
    schemaVersion: SCHEMA_VERSION,
    sourceGeneratedAt: isoFromMs(data?.metadata?.generated),
    sourceMetadata: data?.metadata
      ? {
          title: data.metadata.title || null,
          api: data.metadata.api || null,
          count: finite(data.metadata.count),
          status: finite(data.metadata.status)
        }
      : null,
    simulated: false,
    count: events.length,
    events,
    retrievedAt,
    timestamp: retrievedAt
  };
}

function normalizeEonet(data, sourceUrl, limit = 10, retrievedAt = new Date().toISOString()) {
  const events = (data?.events || [])
    .slice(0, limit)
    .map((event) => {
      const history = Array.isArray(event?.geometry) ? event.geometry : [];
      const latest = history.at(-1) || null;
      const geometry = latest?.type && Array.isArray(latest?.coordinates)
        ? {
            type: latest.type,
            coordinates: latest.coordinates
          }
        : null;
      const position = pointFromGeometry(geometry);
      const sourceId = event?.id || null;
      const title = event?.title || null;
      const categories = (event?.categories || [])
        .map((category) => category?.title)
        .filter(Boolean);
      const time = latest?.date || null;
      const sourceUrlValue = event?.link || sourceUrl;

      return {
        id: sourceId,
        title,
        categories,
        time,
        link: event?.link || null,
        coordinates: position
          ? {
              latitude: position.latitude,
              longitude: position.longitude
            }
          : null,
        geometryHistory: history,
        spine: spineRecord({
          source: "eonet",
          sourceId,
          eventType: categories[0] || "natural-event",
          title,
          geometry,
          position,
          occurredAt: time,
          expiresAt: event?.closed || null,
          sourceUrl: sourceUrlValue,
          retrievedAt,
          sourceMetadata: {
            categories,
            closed: event?.closed || null,
            geometryCount: history.length,
            magnitudeValue: finite(latest?.magnitudeValue),
            magnitudeUnit: latest?.magnitudeUnit || null
          }
        }),
        sourceRecord: {
          id: sourceId,
          title,
          description: event?.description || null,
          link: event?.link || null,
          closed: event?.closed || null,
          categories: event?.categories || [],
          sources: event?.sources || []
        }
      };
    });

  return {
    ok: true,
    source: "eonet",
    sourceUrl,
    schemaVersion: SCHEMA_VERSION,
    sourceGeneratedAt: null,
    sourceMetadata: {
      title: data?.title || null,
      description: data?.description || null,
      link: data?.link || null
    },
    simulated: false,
    count: events.length,
    events,
    retrievedAt,
    timestamp: retrievedAt
  };
}

function normalizeNws(data, sourceUrl, limit = 10, retrievedAt = new Date().toISOString()) {
  const events = (data?.features || [])
    .slice(0, limit)
    .map((feature) => {
      const p = feature?.properties || {};
      const geometry = feature?.geometry || null;
      const position = pointFromGeometry(geometry);
      const sourceId = p.id || feature?.id || null;
      const eventType = p.event || "Weather alert";
      const headline = p.headline || null;
      const sourceUrlValue = p.web || p.uri || p.id || feature?.id || sourceUrl;
      const occurredAt = p.onset || p.effective || p.sent || null;

      return {
        id: sourceId,
        event: eventType,
        headline,
        severity: p.severity || null,
        area: p.areaDesc || null,
        effective: p.effective || null,
        expires: p.expires || null,
        url: sourceUrlValue,
        sent: p.sent || null,
        onset: p.onset || null,
        ends: p.ends || null,
        urgency: p.urgency || null,
        certainty: p.certainty || null,
        status: p.status || null,
        messageType: p.messageType || null,
        coordinates: position
          ? {
              latitude: position.latitude,
              longitude: position.longitude
            }
          : null,
        spine: spineRecord({
          source: "nws",
          sourceId,
          eventType,
          title: headline || eventType,
          severity: p.severity || null,
          geometry,
          position,
          occurredAt,
          updatedAt: p.sent || null,
          expiresAt: p.expires || p.ends || null,
          sourceUrl: sourceUrlValue,
          retrievedAt,
          sourceMetadata: {
            area: p.areaDesc || null,
            urgency: p.urgency || null,
            certainty: p.certainty || null,
            status: p.status || null,
            messageType: p.messageType || null,
            senderName: p.senderName || null,
            response: p.response || null
          }
        }),
        sourceRecord: {
          id: p.id || null,
          type: feature?.type || null,
          properties: {
            areaDesc: p.areaDesc || null,
            geocode: p.geocode || null,
            affectedZones: p.affectedZones || [],
            references: p.references || [],
            sent: p.sent || null,
            effective: p.effective || null,
            onset: p.onset || null,
            expires: p.expires || null,
            ends: p.ends || null,
            status: p.status || null,
            messageType: p.messageType || null,
            category: p.category || null,
            severity: p.severity || null,
            certainty: p.certainty || null,
            urgency: p.urgency || null,
            event: eventType,
            sender: p.sender || null,
            senderName: p.senderName || null,
            headline,
            response: p.response || null,
            parameters: p.parameters || null,
            web: p.web || null,
            uri: p.uri || null
          }
        }
      };
    });

  return {
    ok: true,
    source: "nws",
    sourceUrl,
    schemaVersion: SCHEMA_VERSION,
    sourceGeneratedAt: null,
    sourceMetadata: {
      title: data?.title || null,
      updated: data?.updated || null
    },
    simulated: false,
    count: events.length,
    events,
    retrievedAt,
    timestamp: retrievedAt
  };
}

function normalizeWorldData(source, data, sourceUrl, limit = 10, retrievedAt = new Date().toISOString()) {
  if (source === "usgs") {
    return normalizeUsgs(data, sourceUrl, limit, retrievedAt);
  }

  if (source === "eonet") {
    return normalizeEonet(data, sourceUrl, limit, retrievedAt);
  }

  if (source === "nws") {
    return normalizeNws(data, sourceUrl, limit, retrievedAt);
  }

  throw new Error("Unsupported world-event source");
}

module.exports = {
  SCHEMA_VERSION,
  normalizeUsgs,
  normalizeEonet,
  normalizeNws,
  normalizeWorldData
};
