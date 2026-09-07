"use strict";

const crypto = require("crypto");
const express = require("express");

const DATABASE_URL = process.env.DATABASE_URL || "";
const COMMAND_CENTER_ACCESS_TOKEN =
  process.env.COMMAND_CENTER_ACCESS_TOKEN || "";
const originalListen = express.application.listen;
const rateBuckets = new Map();

let pool = null;
let schemaReady = null;

function clean(value, max = 500) {
  return String(value == null ? "" : value)
    .replace(/\u0000/g, "")
    .trim()
    .slice(0, max);
}

function validEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value);
}

function sameOrigin(req) {
  const origin = req.get("origin");
  const host = req.get("host");

  if (!origin || !host) return true;

  try {
    return new URL(origin).host === host;
  } catch {
    return false;
  }
}

function clientKey(req) {
  const forwarded = String(req.get("x-forwarded-for") || "")
    .split(",")[0]
    .trim();
  return forwarded || req.ip || "unknown";
}

function rateAllowed(req) {
  const now = Date.now();
  const windowMs = 15 * 60 * 1000;
  const max = 5;
  const key = clientKey(req);
  const existing = rateBuckets.get(key);

  if (!existing || now - existing.startedAt >= windowMs) {
    rateBuckets.set(key, { startedAt: now, count: 1 });
    return true;
  }

  existing.count += 1;
  rateBuckets.set(key, existing);
  return existing.count <= max;
}

function secretsMatch(received, expected) {
  if (!received || !expected) return false;

  const a = Buffer.from(received);
  const b = Buffer.from(expected);

  return a.length === b.length && crypto.timingSafeEqual(a, b);
}

function requireLeadAdmin(req, res, next) {
  if (!COMMAND_CENTER_ACCESS_TOKEN) {
    return res.status(503).json({
      ok: false,
      error: "Lead administration is not configured"
    });
  }

  const authorization = req.get("authorization") || "";
  const match = authorization.match(/^Bearer\s+(.+)$/i);

  if (!match || !secretsMatch(match[1], COMMAND_CENTER_ACCESS_TOKEN)) {
    return res.status(401).json({ ok: false, error: "Unauthorized" });
  }

  return next();
}

function getPool() {
  if (!DATABASE_URL) return null;

  if (!pool) {
    const { Pool } = require("pg");
    pool = new Pool({
      connectionString: DATABASE_URL,
      max: 4,
      idleTimeoutMillis: 30000,
      connectionTimeoutMillis: 5000
    });

    pool.on("error", (error) => {
      console.error("lead database pool error", error.message);
    });
  }

  return pool;
}

async function ensureSchema() {
  const db = getPool();
  if (!db) throw new Error("Lead database is not configured");

  if (!schemaReady) {
    schemaReady = db
      .query(`
        CREATE TABLE IF NOT EXISTS eagle_eyes_deployment_leads (
          id UUID PRIMARY KEY,
          created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
          name TEXT NOT NULL,
          email TEXT NOT NULL,
          phone TEXT NOT NULL DEFAULT '',
          company TEXT NOT NULL DEFAULT '',
          deployment_package TEXT NOT NULL,
          timeline TEXT NOT NULL DEFAULT '',
          message TEXT NOT NULL,
          source TEXT NOT NULL DEFAULT 'eagle-eyes-business',
          user_agent TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS eagle_eyes_deployment_leads_created_at_idx
          ON eagle_eyes_deployment_leads (created_at DESC);
      `)
      .catch((error) => {
        schemaReady = null;
        throw error;
      });
  }

  await schemaReady;
  return db;
}

function normalizeLead(body) {
  const name = clean(body?.name, 120);
  const email = clean(body?.email, 160).toLowerCase();
  const phone = clean(body?.phone, 60);
  const company = clean(body?.company, 160);
  const deploymentPackage = clean(body?.package, 80) || "Not sure";
  const timeline = clean(body?.timeline, 80);
  const message = clean(body?.message, 4000);
  const website = clean(body?.website, 240);

  return {
    name,
    email,
    phone,
    company,
    deploymentPackage,
    timeline,
    message,
    website
  };
}

function validateLead(lead) {
  if (lead.website) return { honeypot: true };
  if (lead.name.length < 2) return { error: "Name is required" };
  if (!validEmail(lead.email)) return { error: "A valid email is required" };
  if (lead.message.length < 10) {
    return { error: "Tell us briefly what you want Eagle Eyes to monitor" };
  }
  return {};
}

function registerLeadIntake(app) {
  if (app.locals.__eagleEyesLeadIntakeRegistered) return;
  app.locals.__eagleEyesLeadIntakeRegistered = true;

  app.get("/api/leads/status", (_req, res) => {
    res.json({
      ok: true,
      configured: Boolean(DATABASE_URL),
      storage: DATABASE_URL ? "postgres" : "unconfigured",
      timestamp: new Date().toISOString()
    });
  });

  app.post("/api/leads", async (req, res) => {
    if (!sameOrigin(req)) {
      return res.status(403).json({ ok: false, error: "Invalid origin" });
    }

    if (!rateAllowed(req)) {
      return res.status(429).json({
        ok: false,
        error: "Too many requests. Please try again later."
      });
    }

    const lead = normalizeLead(req.body || {});
    const validation = validateLead(lead);

    if (validation.honeypot) {
      return res.status(201).json({
        ok: true,
        leadId: crypto.randomUUID(),
        received: true
      });
    }

    if (validation.error) {
      return res.status(400).json({ ok: false, error: validation.error });
    }

    try {
      const db = await ensureSchema();
      const leadId = crypto.randomUUID();

      await db.query(
        `INSERT INTO eagle_eyes_deployment_leads
          (id, name, email, phone, company, deployment_package, timeline, message, source, user_agent)
         VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)`,
        [
          leadId,
          lead.name,
          lead.email,
          lead.phone,
          lead.company,
          lead.deploymentPackage,
          lead.timeline,
          lead.message,
          "eagle-eyes-business",
          clean(req.get("user-agent"), 500)
        ]
      );

      console.log(
        JSON.stringify({
          event: "deployment_lead_received",
          leadId,
          deploymentPackage: lead.deploymentPackage,
          createdAt: new Date().toISOString()
        })
      );

      return res.status(201).json({
        ok: true,
        leadId,
        received: true,
        message: "Deployment request received"
      });
    } catch (error) {
      console.error("deployment lead intake failed", error.message);
      return res.status(503).json({
        ok: false,
        error: "Deployment request service is temporarily unavailable"
      });
    }
  });

  app.get("/api/leads", requireLeadAdmin, async (req, res) => {
    try {
      const db = await ensureSchema();
      const requested = Number(req.query.limit || 25);
      const limit = Math.max(1, Math.min(100, Number.isFinite(requested) ? requested : 25));
      const result = await db.query(
        `SELECT id, created_at, name, email, phone, company,
                deployment_package, timeline, message, source
           FROM eagle_eyes_deployment_leads
          ORDER BY created_at DESC
          LIMIT $1`,
        [limit]
      );

      return res.json({
        ok: true,
        count: result.rows.length,
        leads: result.rows,
        timestamp: new Date().toISOString()
      });
    } catch (error) {
      console.error("lead list failed", error.message);
      return res.status(503).json({
        ok: false,
        error: "Lead administration is temporarily unavailable"
      });
    }
  });
}

if (!express.application.__eagleEyesLeadIntakePatched) {
  Object.defineProperty(express.application, "__eagleEyesLeadIntakePatched", {
    value: true,
    enumerable: false,
    configurable: false,
    writable: false
  });

  express.application.listen = function patchedListen(...args) {
    registerLeadIntake(this);
    return originalListen.apply(this, args);
  };
}

module.exports = {
  clean,
  normalizeLead,
  validateLead,
  registerLeadIntake
};
