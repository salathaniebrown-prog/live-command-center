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
  'const {\n  CHAIN_SOURCE_URL,\n  queryEvmChains,\n  formatEvmChains\n} = require("./evm-chains");\n',
  'require("./evm-chains")',
  "EVM import"
);

insertBefore(
  '  {\n    type: "function",\n    name: "get_world_os_status",',
  '  {\n    type: "function",\n    name: "get_evm_chains",\n    description:\n      "Search the canonical ChainID EVM registry by chain name, short name, symbol, CAIP-2 identifier, or chain ID. Metadata is observation-only; never sign or submit transactions.",\n    strict: true,\n    parameters: {\n      type: "object",\n      properties: {\n        query: { type: "string" },\n        limit: { type: "integer", minimum: 1, maximum: 20 }\n      },\n      required: ["query", "limit"],\n      additionalProperties: false\n    }\n  },\n',
  'name: "get_evm_chains"',
  "EVM tool"
);

insertBefore(
  '  "For a mission brief, situation report, broad incident-priority request, or question about what matters now, call get_operational_snapshot before answering.",',
  '  "For EVM chain-registry questions, call get_evm_chains. Treat RPC endpoints, explorers, parent/L2 relationships, status, and red flags as read-only metadata; never connect a wallet, sign a payload, or submit a transaction.",\n',
  'For EVM chain-registry questions',
  "EVM instruction"
);

insertBefore(
  '        "• World OS capability status",',
  '        "• EVM chain registry lookup by chain name or chain ID (read-only)",\n',
  '• EVM chain registry lookup',
  "free help"
);

insertBefore(
  '  if (/\\b(deployment|deploy|railway)\\b/.test(q)) {',
  '  if (/\\b(evm|chain\\s*id|chainid|chain registry|ethereum network|rpc registry)\\b/.test(q)) {\n    try {\n      const data = await queryEvmChains({\n        query: message,\n        limit: 10\n      });\n\n      return {\n        handled: true,\n        tool: "get_evm_chains",\n        text: formatEvmChains(data)\n      };\n    } catch (error) {\n      return {\n        handled: true,\n        tool: "get_evm_chains",\n        text: [\n          "EVM CHAIN REGISTRY TEMPORARILY UNAVAILABLE",\n          `Reason: ${error.message}`,\n          "No simulated chain metadata was substituted."\n        ].join("\\n")\n      };\n    }\n  }\n\n',
  'tool: "get_evm_chains"',
  "free EVM command"
);

insertAfter(
  '        `CelesTrak Weather Satellites: ${CELESTRAK_WEATHER_URL}`,',
  '\n        `EVM Chain Registry: ${CHAIN_SOURCE_URL}`,',
  'EVM Chain Registry: ${CHAIN_SOURCE_URL}',
  "source listing"
);

insertBefore(
  '    case "get_world_os_status":\n      return worldOSStatus();',
  '    case "get_evm_chains":\n      return queryEvmChains({\n        query: args.query,\n        limit: args.limit\n      });\n\n',
  'case "get_evm_chains":',
  "runTool EVM case"
);

insertBefore(
  'app.get(\n  "/api/eagle-eyes/events",',
  'app.get(\n  "/api/eagle-eyes/chains",\n  async (req, res) => {\n    try {\n      res.json(\n        await queryEvmChains({\n          query: req.query.q || req.query.query || "",\n          limit: req.query.limit\n        })\n      );\n    } catch (error) {\n      res.status(502).json({\n        ok: false,\n        source: CHAIN_SOURCE_URL,\n        observationOnly: true,\n        simulated: false,\n        error: error.message,\n        timestamp: new Date().toISOString()\n      });\n    }\n  }\n);\n\n',
  '"/api/eagle-eyes/chains"',
  "EVM API route"
);

const current = fs.readFileSync(serverPath, "utf8");
if (next !== current) {
  fs.writeFileSync(serverPath, next);
  console.log("Eagle Eyes read-only EVM chain registry enabled.");
} else {
  console.log("Eagle Eyes read-only EVM chain registry already enabled.");
}
