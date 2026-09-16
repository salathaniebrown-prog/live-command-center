"use strict";

const SOURCE_ORDER = ["nws", "usgs", "eonet"];
const SOURCE_LABELS = Object.freeze({
  nws: "NOAA/NWS",
  usgs: "USGS",
  eonet: "NASA EONET"
});

const SEVERITY_SCORES = Object.freeze({
  Extreme: 100,
  Severe: 85,
  Moderate: 65,
  Minor: 35,
  Unknown: 20
});

function finite(value) {
  return Number.isFinite(value) ? value : null;
}

function isoOrNull(value) {
  if (!value) return null;
  const time = Date.parse(value);
  return Number.isFinite(time) ? new Date(time).toISOString() : null;
}

function normalizedRecord(event, source) {
  const spine = event?.spine || {};
  const sourceId =
    spine.sourceId ||
    event?.id ||
    event?.sourceId ||
    null;
  const title =
    spine.title ||
    event?.title ||
    event?.headline ||
    event?.event ||
    "Untitled live event";
  const eventType =
    spine.eventType ||
    event?.eventType ||
    event?.event ||
    (source === "usgs" ? "earthquake" : "natural-event");
  const severity =
    spine.severity ||
    event?.severity ||
    null;
  const magnitude = Number.isFinite(spine.magnitude)
    ? spine.magnitude
    : finite(event?.magnitude);
  const occurredAt =
    isoOrNull(spine.occurredAt) ||
    isoOrNull(event?.time) ||
    isoOrNull(event?.onset) ||
    isoOrNull(event?.effective) ||
    null;
  const updatedAt =
    isoOrNull(spine.updatedAt) ||
    isoOrNull(event?.updatedAt) ||
    isoOrNull(event?.sent) ||
    null;
  const expiresAt =
    isoOrNull(spine.expiresAt) ||
    isoOrNull(event?.expires) ||
    isoOrNull(event?.ends) ||
    null;
  const sourceUrl =
    spine.sourceUrl ||
    event?.url ||
    event?.link ||
    null;
  const position =
    spine.position ||
    event?.coordinates ||
    null;
  const metadata =
    spine.sourceMetadata ||
    null;

  const fallbackId = [
    source,
    title,
    eventType,
    occurredAt || "no-time"
  ].join("|");

  return {
    key: `${source}:${sourceId || fallbackId}`,
    source,
    sourceLabel: SOURCE_LABELS[source] || source.toUpperCase(),
    sourceId,
    title,
    eventType,
    severity,
    magnitude,
    occurredAt,
    updatedAt,
    expiresAt,
    sourceUrl,
    position,
    metadata,
    retrievedAt:
      isoOrNull(spine.retrievedAt) ||
      isoOrNull(event?.retrievedAt) ||
      null,
    verification: "DIRECT_SOURCE_NORMALIZED",
    authority: "observation",
    commandEligible: false
  };
}

function fingerprint(record) {
  return JSON.stringify([
    record.title,
    record.eventType,
    record.severity,
    record.magnitude,
    record.occurredAt,
    record.updatedAt,
    record.expiresAt,
    record.position
  ]);
}

function priorityScore(record, nowMs) {
  let score = 20;

  if (record.source === "nws") {
    score = SEVERITY_SCORES[record.severity] || SEVERITY_SCORES.Unknown;
  } else if (record.source === "usgs") {
    const magnitude = record.magnitude;
    score = Number.isFinite(magnitude)
      ? magnitude >= 6
        ? 95
        : magnitude >= 5
          ? 80
          : magnitude >= 4
            ? 65
            : magnitude >= 3
              ? 45
              : 25
      : 20;
  } else if (record.source === "eonet") {
    score = 40;
  }

  if (record.occurredAt) {
    const eventMs = Date.parse(record.occurredAt);
    if (Number.isFinite(eventMs)) {
      const ageMinutes = Math.max(0, (nowMs - eventMs) / 60000);
      if (ageMinutes <= 60) score += 5;
      else if (ageMinutes <= 360) score += 3;
    }
  }

  return Math.min(100, score);
}

function priorityLevel(score) {
  if (score >= 95) return "critical";
  if (score >= 85) return "high";
  if (score >= 65) return "elevated";
  if (score >= 40) return "monitor";
  return "context";
}

function priorityReason(record) {
  if (record.source === "nws") {
    return record.severity
      ? `NWS severity is ${record.severity}.`
      : "NWS severity is unavailable; keep this as contextual monitoring only.";
  }

  if (record.source === "usgs") {
    return Number.isFinite(record.magnitude)
      ? `USGS magnitude is M${record.magnitude}.`
      : "USGS magnitude is unavailable.";
  }

  return "NASA EONET currently lists this event as active in the returned feed window.";
}

function factStatement(record) {
  if (record.source === "nws") {
    const area = record.metadata?.area || "area unavailable";
    return `${record.title} • severity ${record.severity || "unavailable"} • ${area}`;
  }

  if (record.source === "usgs") {
    return `${Number.isFinite(record.magnitude) ? `M${record.magnitude} • ` : ""}${record.title}`;
  }

  return `${record.title} • ${record.eventType}`;
}

function compactChange(record, kind) {
  return {
    kind,
    source: record.source,
    sourceLabel: record.sourceLabel,
    sourceId: record.sourceId,
    title: record.title,
    severity: record.severity,
    magnitude: record.magnitude,
    occurredAt: record.occurredAt,
    updatedAt: record.updatedAt,
    sourceUrl: record.sourceUrl
  };
}

function collectRecords(feeds) {
  const records = [];
  const warnings = [];
  const coverage = {};

  for (const source of SOURCE_ORDER) {
    const feed = feeds?.[source] || null;
    const accepted = feed?.ok === true && feed?.simulated !== true;
    const events = accepted && Array.isArray(feed?.events) ? feed.events : [];

    coverage[source] = {
      ok: accepted,
      count: events.length,
      simulated: feed?.simulated === true,
      error: accepted ? null : feed?.error || "source unavailable"
    };

    if (!accepted) {
      warnings.push(
        feed?.simulated === true
          ? `${SOURCE_LABELS[source]} returned simulated data and was excluded from Scribe.`
          : `${SOURCE_LABELS[source]} is unavailable: ${feed?.error || "no live response"}.`
      );
      continue;
    }

    for (const event of events) {
      records.push(normalizedRecord(event, source));
    }
  }

  coverage.total = records.length;
  return { records, warnings, coverage };
}

function buildChronicleScribe(snapshot, previousBaseline = null, now = new Date()) {
  const generatedAt = new Date(now).toISOString();
  const nowMs = Date.parse(generatedAt);
  const { records, warnings, coverage } = collectRecords(snapshot?.feeds || {});
  const current = new Map(
    records.map((record) => [
      record.key,
      {
        fingerprint: fingerprint(record),
        record
      }
    ])
  );

  const previousEvents = previousBaseline?.events || null;
  const comparisonAvailable = Boolean(previousEvents);
  const newEvents = [];
  const updatedEvents = [];
  const notReturned = [];

  if (comparisonAvailable) {
    for (const [key, currentEntry] of current) {
      const previousEntry = previousEvents[key];
      if (!previousEntry) {
        newEvents.push(compactChange(currentEntry.record, "new"));
      } else if (previousEntry.fingerprint !== currentEntry.fingerprint) {
        updatedEvents.push(compactChange(currentEntry.record, "updated"));
      }
    }

    for (const [key, previousEntry] of Object.entries(previousEvents)) {
      if (!current.has(key)) {
        notReturned.push({
          ...compactChange(previousEntry.record, "not_returned"),
          note: "Not present in the current returned feed window; this is not treated as resolved."
        });
      }
    }
  }

  const priorities = records
    .map((record) => {
      const score = priorityScore(record, nowMs);
      return {
        score,
        level: priorityLevel(score),
        source: record.source,
        sourceLabel: record.sourceLabel,
        title: record.title,
        eventType: record.eventType,
        severity: record.severity,
        magnitude: record.magnitude,
        occurredAt: record.occurredAt,
        sourceUrl: record.sourceUrl,
        why: priorityReason(record)
      };
    })
    .sort((a, b) => b.score - a.score)
    .slice(0, 5);

  const verifiedFacts = records
    .slice()
    .sort((a, b) => priorityScore(b, nowMs) - priorityScore(a, nowMs))
    .slice(0, 6)
    .map((record) => ({
      source: record.source,
      sourceLabel: record.sourceLabel,
      statement: factStatement(record),
      observedAt: record.occurredAt,
      retrievedAt: record.retrievedAt,
      sourceUrl: record.sourceUrl,
      verification: record.verification
    }));

  const unknowns = [...warnings];
  if (!comparisonAvailable) {
    unknowns.push(
      "No prior Scribe baseline is available yet; change detection begins with the next Scribe cycle."
    );
  }
  unknowns.push(
    "Scribe evaluates the returned feed windows only. An event missing from a later window is not assumed resolved."
  );

  const watchNext = [];
  const top = priorities[0];
  if (top?.source === "nws" && ["Extreme", "Severe", "Moderate"].includes(top.severity)) {
    watchNext.push(
      `NWS: watch ${top.title} for severity, area, and expiration changes.`
    );
  }

  const quake = priorities.find(
    (item) => item.source === "usgs" && Number.isFinite(item.magnitude) && item.magnitude >= 4
  );
  if (quake) {
    watchNext.push(
      `USGS: watch ${quake.title} for magnitude, location, and update-time changes.`
    );
  }

  if (newEvents.length) {
    watchNext.push(
      `DELTA: review ${newEvents.length} newly returned live event${newEvents.length === 1 ? "" : "s"}.`
    );
  } else if (updatedEvents.length) {
    watchNext.push(
      `DELTA: review ${updatedEvents.length} changed source record${updatedEvents.length === 1 ? "" : "s"}.`
    );
  }

  if (warnings.length && watchNext.length < 3) {
    watchNext.push("COVERAGE: re-check unavailable official feeds on the next sync.");
  }

  if (!watchNext.length) {
    watchNext.push("Watch the next 60-second source sync for official-feed deltas.");
  }

  const baseline = {
    generatedAt,
    events: Object.fromEntries(current)
  };

  const report = {
    ok: true,
    mode: "LIVE_ONLY",
    authority: "observation",
    commandEligible: false,
    simulated: false,
    generatedAt,
    changeState: comparisonAvailable ? "DELTA" : "BASELINE",
    comparisonAvailable,
    coverage,
    changes: {
      newEvents: newEvents.slice(0, 10),
      updatedEvents: updatedEvents.slice(0, 10),
      notReturned: notReturned.slice(0, 10),
      total: newEvents.length + updatedEvents.length + notReturned.length
    },
    priorities,
    verifiedFacts,
    unknowns,
    watchNext: watchNext.slice(0, 3),
    baseline
  };

  report.text = formatChronicleScribe(report);
  return report;
}

function formatChronicleScribe(report) {
  const lines = [
    "CHRONICLE SCRIBE // LIVE EVIDENCE BRIEF",
    "",
    `STATE: ${report.changeState}`,
    `COVERAGE: NWS ${report.coverage?.nws?.count ?? 0} • USGS ${report.coverage?.usgs?.count ?? 0} • NASA EONET ${report.coverage?.eonet?.count ?? 0}`,
    "",
    "WHAT CHANGED:"
  ];

  if (!report.comparisonAvailable) {
    lines.push("Baseline established. Delta comparison starts on the next cycle.");
  } else if (report.changes.total === 0) {
    lines.push("No source-record delta detected in the current returned windows.");
  } else {
    for (const item of report.changes.newEvents.slice(0, 3)) {
      lines.push(`+ NEW • ${item.sourceLabel} • ${item.title}`);
    }
    for (const item of report.changes.updatedEvents.slice(0, 3)) {
      lines.push(`~ UPDATED • ${item.sourceLabel} • ${item.title}`);
    }
    for (const item of report.changes.notReturned.slice(0, 2)) {
      lines.push(`- WINDOW EXIT • ${item.sourceLabel} • ${item.title} • not treated as resolved`);
    }
  }

  lines.push("", "WHAT MATTERS:");
  if (report.priorities.length) {
    report.priorities.forEach((item, index) => {
      lines.push(
        `${index + 1}. [${item.level.toUpperCase()}] ${item.sourceLabel} • ${item.title}`,
        `   ${item.why}`
      );
    });
  } else {
    lines.push("No live source records were available for prioritization.");
  }

  lines.push("", "VERIFIED SOURCE FACTS:");
  if (report.verifiedFacts.length) {
    report.verifiedFacts.slice(0, 4).forEach((fact, index) => {
      lines.push(
        `${index + 1}. ${fact.sourceLabel} • ${fact.statement}${fact.observedAt ? ` • ${fact.observedAt}` : ""}`
      );
    });
  } else {
    lines.push("No source-grounded facts available in this cycle.");
  }

  lines.push("", "UNKNOWNS / LIMITS:");
  report.unknowns.slice(0, 4).forEach((item, index) => {
    lines.push(`${index + 1}. ${item}`);
  });

  lines.push("", "WATCH NEXT:");
  report.watchNext.forEach((item, index) => {
    lines.push(`${index + 1}. ${item}`);
  });

  lines.push(
    "",
    "Simulation: OFF",
    "Authority: OBSERVATION ONLY",
    `Checked: ${report.generatedAt}`
  );

  return lines.join("\n");
}

module.exports = {
  buildChronicleScribe,
  formatChronicleScribe,
  normalizedRecord,
  fingerprint
};
