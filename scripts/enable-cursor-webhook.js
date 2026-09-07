"use strict";

const fs = require("node:fs");
const path = require("node:path");

const serverPath = path.join(__dirname, "..", "server.js");
let next = fs.readFileSync(serverPath, "utf8");

function insertBefore(anchor, addition, marker, label) {
  if (next.includes(marker)) return;
  const index = next.indexOf(anchor);
  if (index === -1) throw new Error(`Could not find ${label} anchor`);
  next = next.slice(0, index) + addition + next.slice(index);
}

function insertAfter(anchor, addition, marker, label) {
  if (next.includes(marker)) return;
  const index = next.indexOf(anchor);
  if (index === -1) throw new Error(`Could not find ${label} anchor`);
  const end = index + anchor.length;
  next = next.slice(0, end) + addition + next.slice(end);
}

insertBefore(
  'const { execFile } = require("child_process");',
  'const { CursorWebhookStore } = require("./cursor-webhook");\n',
  'require("./cursor-webhook")',
  "Cursor webhook import"
);

insertAfter(
  'const app = express();',
  '\nconst cursorWebhookStore = new CursorWebhookStore();',
  'const cursorWebhookStore = new CursorWebhookStore();',
  "Cursor webhook store"
);

insertBefore(
  'app.use(express.json({ limit: "256kb" }));',
  'app.post(\n  "/api/webhooks/cursor",\n  express.raw({ type: "application/json", limit: "256kb" }),\n  (req, res) => {\n    try {\n      const result = cursorWebhookStore.accept({\n        rawBody: req.body,\n        signature: req.get("x-webhook-signature"),\n        deliveryId: req.get("x-webhook-id"),\n        eventType: req.get("x-webhook-event"),\n        secret: process.env.CURSOR_WEBHOOK_SECRET || ""\n      });\n\n      return res.status(result.duplicate ? 200 : 202).json({\n        ok: true,\n        accepted: true,\n        duplicate: result.duplicate,\n        deliveryId: result.deliveryId,\n        agentId: result.event?.id || null,\n        status: result.event?.status || null,\n        timestamp: new Date().toISOString()\n      });\n    } catch (error) {\n      return res.status(Number(error.statusCode) || 400).json({\n        ok: false,\n        accepted: false,\n        code: error.code || "CURSOR_WEBHOOK_REJECTED",\n        error: error.message,\n        timestamp: new Date().toISOString()\n      });\n    }\n  }\n);\n\n',
  '"/api/webhooks/cursor"',
  "Cursor raw webhook route"
);

insertBefore(
  'app.get(\n  "/api/eagle-eyes/events",',
  'app.get(\n  "/api/eagle-eyes/cursor",\n  requireAssistantAccess,\n  (_req, res) => {\n    res.json(\n      cursorWebhookStore.status({\n        configured: Boolean(process.env.CURSOR_WEBHOOK_SECRET)\n      })\n    );\n  }\n);\n\n',
  '"/api/eagle-eyes/cursor"',
  "Cursor status API route"
);

const current = fs.readFileSync(serverPath, "utf8");

if (next !== current) {
  fs.writeFileSync(serverPath, next);
  console.log("Eagle Eyes Cursor webhook routes enabled.");
} else {
  console.log("Eagle Eyes Cursor webhook routes already enabled.");
}
