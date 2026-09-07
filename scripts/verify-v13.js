const fs = require("fs");
const dashboard = fs.readFileSync("public/index.html", "utf8");
const satellites = fs.readFileSync("satellites.js", "utf8");

const requireText = (text, label) => {
  if (!dashboard.includes(text)) {
    throw new Error(`Chronicle Lab baseline missing: ${label}`);
  }
};

if (!satellites.includes("const MAX_SATELLITES = 512;")) {
  throw new Error("Satellite backend ceiling regressed below recovered 512 limit");
}

requireText("CHRONICLE LAB", "Chronicle Lab identity");
requireText("WORLD", "WORLD navigation");
requireText("LIVE", "LIVE navigation");
requireText("LAB", "LAB navigation");
requireText("INTEL", "INTEL navigation");
requireText("LINKS", "LINKS navigation");
requireText("MAX", "MAX navigation");
requireText("EAGLE EYES MAX", "MAX command rail");
requireText("PX4 OBSERVATION", "PX4 observation panel");
requireText("NO FLIGHT AUTHORITY", "observation-only UI boundary");
requireText("/api/eagle-eyes/satellites?limit=120", "120-satellite dashboard request");

const hasStaticWorldLimits = ["nws", "usgs", "eonet"].every((source) =>
  dashboard.includes(`source=${source}&limit=50`)
);
const hasDynamicWorldLimit = dashboard.includes(
  "const url='/api/eagle-eyes/events?source='+src+'&limit=50';"
);

if (!hasStaticWorldLimits && !hasDynamicWorldLimit) {
  throw new Error("Recovered 50-record live world-event dashboard limit is missing");
}

if (dashboard.includes("COMMAND CENTER • V2") || dashboard.includes("Command Center V2")) {
  throw new Error("Legacy V2 shell regression detected");
}

console.log(
  "Chronicle Lab V13 baseline locked: identity/navigation/MAX/PX4 preserved; satellites 512 backend / 120 dashboard; world feeds 50 each; V2 rollback blocked."
);
