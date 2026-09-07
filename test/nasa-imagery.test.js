"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  EONET_LAYERS_BASE,
  categoryIdsFromEvent,
  layerEndpoint,
  resolveImageryLayers,
  buildImageryManifest
} = require("../nasa-imagery");

test("extracts EONET category ids and builds the v3 layers endpoint", () => {
  const event = {
    id: "EONET_1",
    categories: [{ id: "wildfires" }, { id: "severeStorms" }]
  };

  assert.deepEqual(categoryIdsFromEvent(event), ["wildfires", "severeStorms"]);
  assert.equal(
    layerEndpoint("wildfires"),
    `${EONET_LAYERS_BASE}/wildfires`
  );
});

test("prefers WMTS layers and preserves service metadata", () => {
  const payload = {
    categories: [
      {
        id: "wildfires",
        title: "Wildfires",
        layers: [
          {
            name: "MODIS_Terra_CorrectedReflectance_TrueColor",
            serviceUrl: "https://example.nasa.gov/wmts",
            serviceTypeId: "WMTS_1_0_0",
            parameters: { TIME: "" }
          },
          {
            name: "legacy-wms",
            serviceUrl: "https://example.nasa.gov/wms",
            serviceTypeId: "WMS_1_3_0"
          }
        ]
      }
    ]
  };

  const layers = resolveImageryLayers(payload);
  assert.equal(layers.length, 1);
  assert.equal(layers[0].serviceTypeId, "WMTS_1_0_0");
  assert.equal(layers[0].source, "NASA EONET");
  assert.equal(layers[0].authority, "observation");
  assert.equal(layers[0].commandEligible, false);
});

test("builds an observation-only imagery manifest for an EONET event", () => {
  const event = {
    id: "EONET_99",
    title: "Example Wildfire",
    categories: [{ id: "wildfires", title: "Wildfires" }]
  };

  const manifest = buildImageryManifest(
    event,
    {
      wildfires: {
        categories: [
          {
            id: "wildfires",
            title: "Wildfires",
            layers: [
              {
                name: "VIIRS_SNPP_CorrectedReflectance_TrueColor",
                serviceUrl: "https://example.nasa.gov/wmts",
                serviceTypeId: "WMTS_1_0_0",
                parameters: {}
              }
            ]
          }
        ]
      }
    }
  );

  assert.equal(manifest.eventId, "EONET_99");
  assert.equal(manifest.layerCount, 1);
  assert.equal(manifest.simulated, false);
  assert.equal(manifest.authority, "observation");
  assert.equal(manifest.commandEligible, false);
});
