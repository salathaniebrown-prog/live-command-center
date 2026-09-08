"use strict";

const EONET_LAYERS_BASE = "https://eonet.gsfc.nasa.gov/api/v3/layers";

function categoryIdsFromEvent(event) {
  return (Array.isArray(event?.categories) ? event.categories : [])
    .map((category) => String(category?.id || "").trim())
    .filter(Boolean);
}

function layerEndpoint(categoryId) {
  const id = String(categoryId || "").trim();
  if (!id) {
    throw new Error("EONET category id is required");
  }
  return `${EONET_LAYERS_BASE}/${encodeURIComponent(id)}`;
}

function normalizeLayer(layer, category = null) {
  if (!layer || typeof layer !== "object") return null;

  const name = String(layer.name || "").trim();
  const serviceUrl = String(layer.serviceUrl || "").trim();
  const serviceTypeId = String(layer.serviceTypeId || "").trim();

  if (!name || !serviceUrl || !serviceTypeId) return null;

  return {
    name,
    serviceUrl,
    serviceTypeId,
    parameters:
      layer.parameters && typeof layer.parameters === "object"
        ? layer.parameters
        : {},
    category: category
      ? {
          id: category.id ?? null,
          title: category.title || null
        }
      : null,
    source: "NASA EONET",
    authority: "observation",
    commandEligible: false
  };
}

function resolveImageryLayers(payload, options = {}) {
  const preferredServiceTypes = new Set(
    (options.preferredServiceTypes || ["WMTS_1_0_0"])
      .map((value) => String(value || "").trim())
      .filter(Boolean)
  );

  const maxLayers = Math.max(1, Math.min(25, Number(options.maxLayers) || 8));
  const categories = Array.isArray(payload?.categories) ? payload.categories : [];
  const layers = [];

  for (const category of categories) {
    for (const rawLayer of Array.isArray(category?.layers) ? category.layers : []) {
      const layer = normalizeLayer(rawLayer, category);
      if (!layer) continue;
      if (preferredServiceTypes.size && !preferredServiceTypes.has(layer.serviceTypeId)) {
        continue;
      }
      layers.push(layer);
      if (layers.length >= maxLayers) return layers;
    }
  }

  return layers;
}

function buildImageryManifest(event, layerPayloadsByCategory, options = {}) {
  const categoryIds = categoryIdsFromEvent(event);
  const layers = [];

  for (const categoryId of categoryIds) {
    const payload = layerPayloadsByCategory?.[categoryId];
    if (!payload) continue;
    layers.push(...resolveImageryLayers(payload, options));
  }

  return {
    eventId: event?.id || null,
    title: event?.title || null,
    categories: categoryIds,
    layerCount: layers.length,
    layers,
    source: "NASA EONET",
    sourceType: "near-real-time event metadata + imagery service references",
    simulated: false,
    authority: "observation",
    commandEligible: false
  };
}

module.exports = {
  EONET_LAYERS_BASE,
  categoryIdsFromEvent,
  layerEndpoint,
  normalizeLayer,
  resolveImageryLayers,
  buildImageryManifest
};
