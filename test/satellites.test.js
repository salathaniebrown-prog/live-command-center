"use strict";

const test =
  require("node:test");
const assert =
  require("node:assert/strict");

const {
  MAX_SATELLITES,
  projectWeatherOmms
} = require("../satellites");

const sample = {
  OBJECT_NAME: "HELIOS 2A",
  OBJECT_ID: "2004-049A",
  EPOCH: "2025-03-26T05:19:34.116960",
  MEAN_MOTION: 15.00555103,
  ECCENTRICITY: 0.000583,
  INCLINATION: 98.3164,
  RA_OF_ASC_NODE: 103.8411,
  ARG_OF_PERICENTER: 20.5667,
  MEAN_ANOMALY: 339.5789,
  EPHEMERIS_TYPE: 0,
  CLASSIFICATION_TYPE: "U",
  NORAD_CAT_ID: 28492,
  ELEMENT_SET_NO: 999,
  REV_AT_EPOCH: 8655,
  BSTAR: 0.00048021,
  MEAN_MOTION_DOT: 0.00005995,
  MEAN_MOTION_DDOT: 0
};

test(
  "projects OMM data into real geodetic coordinates",
  async () => {
    const result =
      await projectWeatherOmms(
        [sample],
        1,
        new Date(
          "2025-03-26T05:30:00.000Z"
        )
      );

    assert.equal(
      result.length,
      1
    );

    assert.equal(
      result[0].noradId,
      "28492"
    );

    assert.ok(
      Number.isFinite(
        result[0].latitude
      )
    );

    assert.ok(
      Number.isFinite(
        result[0].longitude
      )
    );

    assert.ok(
      Number.isFinite(
        result[0].altitudeKm
      )
    );
  }
);

test(
  "caps the orbital display at 30 satellites",
  async () => {
    const records =
      Array.from(
        {
          length:
            MAX_SATELLITES + 8
        },
        (_, index) => ({
          ...sample,
          OBJECT_NAME:
            "TEST " + index,
          NORAD_CAT_ID:
            28492 + index
        })
      );

    const result =
      await projectWeatherOmms(
        records,
        999,
        new Date(
          "2025-03-26T05:30:00.000Z"
        )
      );

    assert.equal(
      result.length,
      MAX_SATELLITES
    );
  }
);
