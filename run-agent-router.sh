#!/bin/bash
export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-sk-or-v1-placeholder}"
export ASTRA_TELEMETRY_ENGINE="active"
export CRYPTOGRAPHIC_LEDGER="astra_ledger.db"

echo "[+] Initializing Unified OpenRouter Agent CLI & Cryptographic Telemetry Gateway..."
node -e '
const http = require("http");
const server = http.createServer((req, res) => {
  res.writeHead(200, { "Content-Type": "application/json" });
  res.end(JSON.stringify({
    status: "ONLINE",
    engine: "OpenRouter & Cryptographic Ledger",
    timestamp: new Date().toISOString()
  }));
});
server.listen(9090, () => {
  console.log("[+] Agent CLI bridge active on http://127.0.0.1:9090");
});
'
