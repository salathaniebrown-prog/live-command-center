"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

const serverPath =
  path.join(
    __dirname,
    "..",
    "server.js"
  );

const original =
  fs.readFileSync(
    serverPath,
    "utf8"
  );

let next =
  original;

function insertBefore(
  anchor,
  addition,
  marker,
  label
) {
  if (next.includes(marker)) {
    return;
  }

  const index =
    next.indexOf(anchor);

  if (index === -1) {
    throw new Error(
      `Deep Security patch refused: ${label} anchor not found`
    );
  }

  next =
    next.slice(0, index) +
    addition +
    next.slice(index);
}

function insertAfter(
  anchor,
  addition,
  marker,
  label
) {
  if (next.includes(marker)) {
    return;
  }

  const index =
    next.indexOf(anchor);

  if (index === -1) {
    throw new Error(
      `Deep Security patch refused: ${label} anchor not found`
    );
  }

  const end =
    index + anchor.length;

  next =
    next.slice(0, end) +
    addition +
    next.slice(end);
}

insertBefore(
  'const { execFile } = require("child_process");',
  [
    'const {',
    '  createDeepSecurityFromEnv',
    '} = require("./deep-security");',
    ''
  ].join("\n"),
  'require("./deep-security")',
  "module import"
);

insertAfter(
  'const OPENAI_URL = "https://api.openai.com/v1/responses";',
  [
    '',
    'const deepSecurity =',
    '  createDeepSecurityFromEnv();'
  ].join("\n"),
  "createDeepSecurityFromEnv();",
  "client initialization"
);

const toolAnchor =
  [
    '  {',
    '    type: "function",',
    '    name: "get_world_os_status",'
  ].join("\n");

const deepSecurityTools =
  [
    '  {',
    '    type: "function",',
    '    name: "get_deep_security_status",',
    '    description:',
    '      "Get Deep Security integration configuration and action-lock status.",',
    '    strict: true,',
    '    parameters: EMPTY',
    '  },',
    '  {',
    '    type: "function",',
    '    name: "deep_security_run_scan",',
    '    description:',
    '      "Execute an authorized Deep Security recommendation, malware, integrity, or open-port scan now.",',
    '    strict: true,',
    '    parameters: {',
    '      type: "object",',
    '      properties: {',
    '        scanType: {',
    '          type: "string",',
    '          enum: ["recommendations", "malware", "integrity", "open-ports"]',
    '        },',
    '        targetType: {',
    '          type: "string",',
    '          enum: ["all-computers", "computer", "computers-in-group", "computers-in-group-or-subgroup", "computers-using-policy", "computers-using-policy-or-subpolicy", "computers-in-smart-folder"]',
    '        },',
    '        targetId: {',
    '          type: "integer",',
    '          minimum: 0',
    '        }',
    '      },',
    '      required: ["scanType", "targetType", "targetId"],',
    '      additionalProperties: false',
    '    }',
    '  },',
    '  {',
    '    type: "function",',
    '    name: "deep_security_add_firewall_rules_to_computer",',
    '    description:',
    '      "Assign existing Deep Security firewall rule IDs to one authorized computer.",',
    '    strict: true,',
    '    parameters: {',
    '      type: "object",',
    '      properties: {',
    '        computerID: { type: "integer", minimum: 1 },',
    '        ruleIDs: {',
    '          type: "array",',
    '          minItems: 1,',
    '          items: { type: "integer", minimum: 1 }',
    '        }',
    '      },',
    '      required: ["computerID", "ruleIDs"],',
    '      additionalProperties: false',
    '    }',
    '  },',
    '  {',
    '    type: "function",',
    '    name: "deep_security_add_firewall_rules_to_policy",',
    '    description:',
    '      "Assign existing Deep Security firewall rule IDs to one authorized policy.",',
    '    strict: true,',
    '    parameters: {',
    '      type: "object",',
    '      properties: {',
    '        policyID: { type: "integer", minimum: 1 },',
    '        ruleIDs: {',
    '          type: "array",',
    '          minItems: 1,',
    '          items: { type: "integer", minimum: 1 }',
    '        }',
    '      },',
    '      required: ["policyID", "ruleIDs"],',
    '      additionalProperties: false',
    '    }',
    '  },',
    '  {',
    '    type: "function",',
    '    name: "deep_security_set_policy_setting",',
    '    description:',
    '      "Set one named Deep Security policy setting on an authorized policy.",',
    '    strict: true,',
    '    parameters: {',
    '      type: "object",',
    '      properties: {',
    '        policyID: { type: "integer", minimum: 1 },',
    '        name: { type: "string" },',
    '        value: { type: "string" }',
    '      },',
    '      required: ["policyID", "name", "value"],',
    '      additionalProperties: false',
    '    }',
    '  },',
    '  {',
    '    type: "function",',
    '    name: "deep_security_sync_aws_connector",',
    '    description:',
    '      "Immediately synchronize one existing authorized AWS connector in Deep Security.",',
    '    strict: true,',
    '    parameters: {',
    '      type: "object",',
    '      properties: {',
    '        awsConnectorID: { type: "integer", minimum: 1 }',
    '      },',
    '      required: ["awsConnectorID"],',
    '      additionalProperties: false',
    '    }',
    '  },',
    ''
  ].join("\n");

insertBefore(
  toolAnchor,
  deepSecurityTools,
  'name: "deep_security_run_scan"',
  "tool definitions"
);

insertBefore(
  '  "Never invent telemetry, alerts, sensor values, or deployment state.",',
  [
    '  "Deep Security is the action-capable protection plane for authorized connected workloads. Use its action tools when the user asks to scan, protect, apply a security setting, assign firewall rules, or synchronize a connector.",',
    '  "Deep Security action tools are intentionally allowlisted. Never use them to create/delete administrators, rotate/delete API keys, delete policies, remove protection, or act on systems that are not authorized and connected.",'
  ].join("\n") + "\n",
  "Deep Security is the action-capable protection plane",
  "instructions"
);

if (
  next.includes(
    '  "All tools are read-only; never claim you changed infrastructure, files, credentials, accounts, or deployments."'
  )
) {
  next =
    next.replace(
      '  "All tools are read-only; never claim you changed infrastructure, files, credentials, accounts, or deployments."',
      '  "Most tools are read-only. Deep Security tools may execute only the explicit allowlisted security actions when DEEP_SECURITY_ACTIONS_ENABLED=true. Report the actual upstream result and never claim an action succeeded unless Deep Security confirms it."'
    );
}

const runToolAnchor =
  [
    '    case "get_world_os_status":',
    '      return worldOSStatus();'
  ].join("\n");

const runToolCases =
  [
    '    case "get_deep_security_status":',
    '      return deepSecurity.configuration();',
    '',
    '    case "deep_security_run_scan": {',
    '      const target = {',
    '        type: args.targetType',
    '      };',
    '',
    '      if (args.targetType === "computer") {',
    '        target.computerID = args.targetId;',
    '      } else if (',
    '        args.targetType === "computers-in-group" ||',
    '        args.targetType === "computers-in-group-or-subgroup"',
    '      ) {',
    '        target.computerGroupID = args.targetId;',
    '      } else if (',
    '        args.targetType === "computers-using-policy" ||',
    '        args.targetType === "computers-using-policy-or-subpolicy"',
    '      ) {',
    '        target.policyID = args.targetId;',
    '      } else if (',
    '        args.targetType === "computers-in-smart-folder"',
    '      ) {',
    '        target.smartFolderID = args.targetId;',
    '      }',
    '',
    '      return deepSecurity.runScan({',
    '        scanType: args.scanType,',
    '        target',
    '      });',
    '    }',
    '',
    '    case "deep_security_add_firewall_rules_to_computer":',
    '      return deepSecurity.addFirewallRulesToComputer(',
    '        args.computerID,',
    '        args.ruleIDs',
    '      );',
    '',
    '    case "deep_security_add_firewall_rules_to_policy":',
    '      return deepSecurity.addFirewallRulesToPolicy(',
    '        args.policyID,',
    '        args.ruleIDs',
    '      );',
    '',
    '    case "deep_security_set_policy_setting":',
    '      return deepSecurity.setPolicySetting(',
    '        args.policyID,',
    '        args.name,',
    '        args.value',
    '      );',
    '',
    '    case "deep_security_sync_aws_connector":',
    '      return deepSecurity.syncAwsConnector(',
    '        args.awsConnectorID',
    '      );',
    ''
  ].join("\n");

insertBefore(
  runToolAnchor,
  runToolCases,
  'case "deep_security_run_scan":',
  "runTool cases"
);

const routesAnchor =
  [
    'app.get(',
    '  "/api/eagle-eyes/events",'
  ].join("\n");

const deepSecurityRoutes =
  [
    'app.get(',
    '  "/api/eagle-eyes/deep-security/status",',
    '  requireAssistantAccess,',
    '  (_req, res) =>',
    '    res.json(',
    '      deepSecurity.configuration()',
    '    )',
    ');',
    '',
    'app.post(',
    '  "/api/eagle-eyes/deep-security/action",',
    '  requireAssistantAccess,',
    '  async (req, res) => {',
    '    try {',
    '      const action =',
    '        String(',
    '          req.body?.action || ""',
    '        ).trim();',
    '',
    '      const args =',
    '        req.body?.args || {};',
    '',
    '      let result;',
    '',
    '      switch (action) {',
    '        case "run-scan":',
    '          result =',
    '            await deepSecurity.runScan(args);',
    '          break;',
    '',
    '        case "add-firewall-rules-to-computer":',
    '          result =',
    '            await deepSecurity.addFirewallRulesToComputer(',
    '              args.computerID,',
    '              args.ruleIDs',
    '            );',
    '          break;',
    '',
    '        case "add-firewall-rules-to-policy":',
    '          result =',
    '            await deepSecurity.addFirewallRulesToPolicy(',
    '              args.policyID,',
    '              args.ruleIDs',
    '            );',
    '          break;',
    '',
    '        case "set-policy-setting":',
    '          result =',
    '            await deepSecurity.setPolicySetting(',
    '              args.policyID,',
    '              args.name,',
    '              args.value',
    '            );',
    '          break;',
    '',
    '        case "sync-aws-connector":',
    '          result =',
    '            await deepSecurity.syncAwsConnector(',
    '              args.awsConnectorID',
    '            );',
    '          break;',
    '',
    '        default:',
    '          return res.status(400).json({',
    '            ok: false,',
    '            error:',
    '              "Unsupported Deep Security action"',
    '          });',
    '      }',
    '',
    '      return res.json({',
    '        ok: true,',
    '        action,',
    '        result,',
    '        timestamp:',
    '          new Date().toISOString()',
    '      });',
    '    } catch (error) {',
    '      const statusCode =',
    '        Number(error.statusCode);',
    '',
    '      return res',
    '        .status(',
    '          statusCode >= 400 && statusCode < 600',
    '            ? statusCode',
    '            : 502',
    '        )',
    '        .json({',
    '          ok: false,',
    '          error:',
    '            error.message,',
    '          timestamp:',
    '            new Date().toISOString()',
    '        });',
    '    }',
    '  }',
    ');',
    ''
  ].join("\n");

insertBefore(
  routesAnchor,
  deepSecurityRoutes,
  '"/api/eagle-eyes/deep-security/action"',
  "HTTP action routes"
);

if (
  next.includes(
    "      readOnlyTools:\n        TOOLS.map("
  )
) {
  next =
    next.replace(
      "      readOnlyTools:\n        TOOLS.map(",
      [
        "      deepSecurity:",
        "        deepSecurity.configuration(),",
        "",
        "      actionTools:",
        "        TOOLS.filter(",
        "          (t) =>",
        "            t.name?.startsWith(",
        '              "deep_security_"',
        "            )",
        "        ).map(",
        "          (t) => t.name",
        "        ),",
        "",
        "      tools:",
        "        TOOLS.map("
      ].join("\n")
    );
}

const check =
  spawnSync(
    process.execPath,
    [
      "--check",
      serverPath
    ],
    {
      encoding: "utf8"
    }
  );

if (
  check.status !== 0
) {
  fs.writeFileSync(
    serverPath,
    original,
    "utf8"
  );

  console.error(
    "Deep Security action patch validation failed; original server.js restored."
  );

  console.error(
    check.stderr ||
    check.stdout ||
    "Unknown syntax error"
  );

  process.exit(1);
}

if (
  next !== original
) {
  fs.writeFileSync(
    serverPath,
    next,
    "utf8"
  );
}

console.log(
  "Eagle Eyes Deep Security action layer enabled and syntax-validated."
);
