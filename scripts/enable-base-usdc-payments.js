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

insertBefore(
  'const { execFile } = require("child_process");',
  'const {\n  getCryptoStatus,\n  createPaymentRequest\n} = require("./crypto-payments");\n',
  'require("./crypto-payments")',
  "crypto payments import"
);

insertBefore(
  'app.get(\n  "/api/eagle-eyes/events",',
  'app.get(\n  "/api/eagle-eyes/crypto/status",\n  (req, res) => {\n    res.json(getCryptoStatus());\n  }\n);\n\napp.post(\n  "/api/eagle-eyes/crypto/payment-request",\n  requireAssistantAccess,\n  (req, res) => {\n    try {\n      res.json(\n        createPaymentRequest({\n          amountUsdc: req.body?.amountUsdc,\n          memo: req.body?.memo\n        })\n      );\n    } catch (error) {\n      const configurationError = /CRYPTO_RECEIVE_ADDRESS|mainnet is locked/.test(\n        error.message\n      );\n\n      res.status(configurationError ? 503 : 400).json({\n        ok: false,\n        error: error.message,\n        transactionCreated: false,\n        transactionSigned: false,\n        transactionSubmitted: false,\n        timestamp: new Date().toISOString()\n      });\n    }\n  }\n);\n\n',
  '"/api/eagle-eyes/crypto/payment-request"',
  "crypto payments API routes"
);

const current = fs.readFileSync(serverPath, "utf8");
if (next !== current) {
  fs.writeFileSync(serverPath, next);
  console.log("Eagle Eyes Base USDC receive-only payment routes enabled.");
} else {
  console.log("Eagle Eyes Base USDC receive-only payment routes already enabled.");
}
