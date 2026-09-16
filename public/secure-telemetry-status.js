"use strict";

(() => {
  const ENDPOINT = "/api/eagle-eyes/telemetry-integrity";

  function ensurePill() {
    const host = document.querySelector(".topPills");
    if (!host) return null;
    let pill = document.getElementById("telemetryIntegrityPill");
    if (!pill) {
      pill = document.createElement("div");
      pill.id = "telemetryIntegrityPill";
      pill.className = "pill warn";
      pill.innerHTML = '<span class="dot"></span>TELEMETRY CHECK';
      host.appendChild(pill);
    }
    return pill;
  }

  function ensureFacts() {
    const host = document.querySelector("#links .facts");
    if (!host) return null;

    let integrity = document.getElementById("telemetryIntegrityFact");
    if (!integrity) {
      integrity = document.createElement("div");
      integrity.id = "telemetryIntegrityFact";
      integrity.className = "fact";
      integrity.innerHTML = '<span>Secure telemetry</span><b>CHECK</b>';
      host.appendChild(integrity);
    }

    let ledger = document.getElementById("telemetryLedgerFact");
    if (!ledger) {
      ledger = document.createElement("div");
      ledger.id = "telemetryLedgerFact";
      ledger.className = "fact";
      ledger.innerHTML = '<span>Signed ledger</span><b>CHECK</b>';
      host.appendChild(ledger);
    }

    return { integrity, ledger };
  }

  function paint(payload) {
    const pill = ensurePill();
    const facts = ensureFacts();
    if (!pill || !facts) return;

    const state = payload?.state || "UNAVAILABLE";
    let klass = "warn";
    let label = "TELEMETRY UNAVAILABLE";

    if (state === "LIVE_VERIFIED") {
      klass = "good";
      label = "SIGNED • VERIFIED • LIVE";
    } else if (state === "SIGNED_READY") {
      klass = "good";
      label = "SIGNED • VERIFIED • READY";
    } else if (state === "UNCONFIGURED") {
      klass = "warn";
      label = "TELEMETRY UNCONFIGURED";
    } else if (state === "UNVERIFIED") {
      klass = "bad";
      label = "TELEMETRY UNVERIFIED";
    }

    pill.className = `pill ${klass}`;
    pill.innerHTML = `<span class="dot"></span>${label}`;

    const integrityOk =
      payload?.integrity?.hmacConfigured === true &&
      payload?.integrity?.replayProtected === true &&
      payload?.integrity?.ledgerWal === true;

    facts.integrity.querySelector("b").textContent = integrityOk
      ? "HMAC + REPLAY LOCK"
      : state;

    const total = payload?.records?.total;
    const live = payload?.records?.live;
    facts.ledger.querySelector("b").textContent =
      Number.isInteger(total) && Number.isInteger(live)
        ? `${live} LIVE / ${total} TOTAL`
        : payload?.integrity?.ledgerWal === true
          ? "WAL READY"
          : "N/A";
  }

  async function refresh() {
    try {
      const response = await fetch(ENDPOINT, { cache: "no-store" });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      paint(await response.json());
    } catch {
      paint({ state: "UNAVAILABLE" });
    }
  }

  ensurePill();
  ensureFacts();
  refresh();
  setInterval(refresh, 30000);
})();
