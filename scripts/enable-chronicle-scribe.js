"use strict";

const fs = require("fs");
const path = require("path");
const vm = require("vm");
const { spawnSync } = require("child_process");

const root = path.join(__dirname, "..");
const serverPath = path.join(root, "server.js");
const dashboardPath = path.join(root, "public", "index.html");
const originalServer = fs.readFileSync(serverPath, "utf8");
const originalDashboard = fs.readFileSync(dashboardPath, "utf8");
let server = originalServer;
let dashboard = originalDashboard;

function requireAnchor(text, anchor, label) {
  if (!text.includes(anchor)) {
    throw new Error(`Chronicle Scribe patch refused: ${label} anchor not found`);
  }
}

const requireLine =
  'const { buildChronicleScribe } = require("./chronicle-scribe");';
if (!server.includes(requireLine)) {
  const anchor = 'const { normalizeWorldData } = require("./data-spine");';
  requireAnchor(server, anchor, "data-spine require");
  server = server.replace(anchor, `${anchor}\n${requireLine}`);
}

const baselineState = "let chronicleScribeBaseline = null;";
if (!server.includes(baselineState)) {
  const anchor = 'const OPENAI_URL = "https://api.openai.com/v1/responses";';
  requireAnchor(server, anchor, "OpenAI URL");
  server = server.replace(anchor, `${anchor}\n${baselineState}`);
}

const toolMarker = 'name: "get_chronicle_scribe"';
if (!server.includes(toolMarker)) {
  const anchor = [
    "  {",
    '    type: "function",',
    '    name: "get_world_os_status",'
  ].join("\n");
  requireAnchor(server, anchor, "World OS tool");

  const tool = [
    "  {",
    '    type: "function",',
    '    name: "get_chronicle_scribe",',
    "    description:",
    '      "Build a read-only Chronicle Scribe brief from current official NWS, USGS, and NASA EONET feed windows, including source-grounded facts, priorities, and delta detection against the previous in-memory Scribe cycle. Never infer resolution from an event leaving the returned window.",',
    "    strict: true,",
    "    parameters: EMPTY",
    "  },",
    ""
  ].join("\n");

  server = server.replace(anchor, tool + anchor);
}

const instructionMarker =
  "For Chronicle Scribe requests, call get_chronicle_scribe";
if (!server.includes(instructionMarker)) {
  const anchor =
    '  "For a mission brief, situation report, broad incident-priority request, or question about what matters now, call get_operational_snapshot before answering.",';
  requireAnchor(server, anchor, "mission brief instruction");
  const line =
    '  "For Chronicle Scribe requests, call get_chronicle_scribe and preserve its distinction between verified source facts, interpretation, unknowns, and feed-window limits.",';
  server = server.replace(anchor, `${anchor}\n${line}`);
}

const helperMarker = "async function chronicleScribeReport()";
if (!server.includes(helperMarker)) {
  const anchor = "function severityScore(severity) {";
  requireAnchor(server, anchor, "severity helper");

  const helper = [
    "async function chronicleScribeReport() {",
    "  const [usgsResult, nwsResult, eonetResult] = await Promise.allSettled([",
    '    world("usgs", 20),',
    '    world("nws", 20),',
    '    world("eonet", 20)',
    "  ]);",
    "",
    "  const asFeed = (result, source) =>",
    '    result.status === "fulfilled"',
    "      ? result.value",
    "      : {",
    "          ok: false,",
    "          source,",
    "          simulated: false,",
    "          count: 0,",
    "          events: [],",
    '          error: result.reason?.message || "source unavailable",',
    "          timestamp: new Date().toISOString()",
    "        };",
    "",
    "  const built = buildChronicleScribe(",
    "    {",
    "      feeds: {",
    '        usgs: asFeed(usgsResult, "usgs"),',
    '        nws: asFeed(nwsResult, "nws"),',
    '        eonet: asFeed(eonetResult, "eonet")',
    "      }",
    "    },",
    "    chronicleScribeBaseline",
    "  );",
    "",
    "  chronicleScribeBaseline = built.baseline;",
    "  const { baseline, ...report } = built;",
    "  return report;",
    "}",
    ""
  ].join("\n");

  server = server.replace(anchor, helper + anchor);
}

const freeMarker = 'tool: "get_chronicle_scribe"';
if (!server.includes(freeMarker)) {
  const anchor = [
    "  if (",
    "    /\\b(mission brief|situation report|sitrep|operational snapshot|priority brief|prioritize incidents|what matters now)\\b/.test(q)",
    "  ) {"
  ].join("\n");
  requireAnchor(server, anchor, "free-command mission brief");

  const block = [
    "  if (",
    "    /\\b(chronicle scribe|scribe brief|what changed|scribe)\\b/.test(q)",
    "  ) {",
    "    const report = await chronicleScribeReport();",
    "    return {",
    "      handled: true,",
    '      tool: "get_chronicle_scribe",',
    "      text: report.text",
    "    };",
    "  }",
    "",
  ].join("\n");

  server = server.replace(anchor, block + anchor);
}

const runToolMarker = 'case "get_chronicle_scribe":';
if (!server.includes(runToolMarker)) {
  const anchor = '    case "get_world_os_status":';
  requireAnchor(server, anchor, "runTool World OS case");
  const block = [
    '    case "get_chronicle_scribe":',
    "      return chronicleScribeReport();",
    "",
  ].join("\n");
  server = server.replace(anchor, block + anchor);
}

const routeMarker = '"/api/eagle-eyes/chronicle/scribe"';
if (!server.includes(routeMarker)) {
  const anchor = 'app.get(\n  "/api/eagle-eyes/satellites",';
  requireAnchor(server, anchor, "satellite route");
  const route = [
    "app.get(",
    '  "/api/eagle-eyes/chronicle/scribe",',
    "  async (_req, res) => {",
    "    try {",
    '      res.set("cache-control", "no-store");',
    "      res.json(await chronicleScribeReport());",
    "    } catch (error) {",
    "      res.status(502).json({",
    "        ok: false,",
    '        mode: "LIVE_ONLY",',
    '        authority: "observation",',
    "        commandEligible: false,",
    "        simulated: false,",
    "        error: error.message,",
    "        timestamp: new Date().toISOString()",
    "      });",
    "    }",
    "  }",
    ");",
    ""
  ].join("\n");
  server = server.replace(anchor, route + anchor);
}

const scribePanelMarker = "CHRONICLE SCRIBE // LIVE SYNTHESIS";
if (!dashboard.includes(scribePanelMarker)) {
  const anchor = '<article id="intel" class="panel span5">';
  requireAnchor(dashboard, anchor, "Executive Chief panel");
  const panel = [
    '<article class="panel span12"><div class="head"><div class="title">CHRONICLE SCRIBE // LIVE SYNTHESIS</div><div id="scribeState" class="sub">ESTABLISHING BASELINE</div></div><div class="body"><div id="scribe" class="executive"><span class="placeholder">Scribe is establishing a source-grounded baseline from NOAA/NWS, USGS, and NASA EONET. No simulated records are accepted.</span></div></div></article>',
    " "
  ].join("\n");
  dashboard = dashboard.replace(anchor, panel + anchor);
}

const stateOld =
  "const S={events:{usgs:[],eonet:[],nws:[]},satellites:[],hits:[],status:null,metrics:null,deployment:null,assistant:null};";
const stateNew =
  "const S={events:{usgs:[],eonet:[],nws:[]},satellites:[],hits:[],status:null,metrics:null,deployment:null,assistant:null,scribe:null};";
if (!dashboard.includes("scribe:null")) {
  requireAnchor(dashboard, stateOld, "dashboard state");
  dashboard = dashboard.replace(stateOld, stateNew);
}

const precedenceOld =
  "esc(e?.severity||e?.magnitude!=null?'M '+e.magnitude:e?.eventType||'LIVE')";
const precedenceNew =
  "esc(e?.severity||(e?.magnitude!=null?'M '+e.magnitude:e?.eventType||'LIVE'))";
if (dashboard.includes(precedenceOld)) {
  dashboard = dashboard.replace(precedenceOld, precedenceNew);
}

const loadScribeMarker = "async function loadScribe()";
if (!dashboard.includes(loadScribeMarker)) {
  const anchor = "async function loadCore(){";
  requireAnchor(dashboard, anchor, "loadCore function");
  const fn = [
    "async function loadScribe(){try{const {r,j}=await getj('/api/eagle-eyes/chronicle/scribe');if(!r.ok)throw new Error(j?.error||'HTTP '+r.status);S.scribe=j||{};const total=Number(j?.changes?.total||0);$('scribeState').textContent=j?.changeState==='DELTA'?(total?total+' SOURCE DELTAS':'NO MATERIAL DELTA'):'BASELINE ESTABLISHED';$('scribe').textContent=j?.text||'Chronicle Scribe returned no narrative.'}catch(e){S.scribe=null;$('scribeState').textContent='UNAVAILABLE';$('scribe').textContent='Chronicle Scribe unavailable: '+e.message+'\\nNo simulated data was substituted.'}}",
    ""
  ].join("\n");
  dashboard = dashboard.replace(anchor, fn + anchor);
}

const syncOld =
  "renderChronicle();drawMap();$('lastSync').textContent='SYNC '+new Date().toLocaleTimeString();loadPx4()";
const syncNew =
  "renderChronicle();drawMap();await loadScribe();$('lastSync').textContent='SYNC '+new Date().toLocaleTimeString();loadPx4()";
if (!dashboard.includes("await loadScribe();$('lastSync')")) {
  requireAnchor(dashboard, syncOld, "syncAll Scribe hook");
  dashboard = dashboard.replace(syncOld, syncNew);
}

fs.writeFileSync(serverPath, server, "utf8");
fs.writeFileSync(dashboardPath, dashboard, "utf8");

const serverCheck = spawnSync(process.execPath, ["--check", serverPath], {
  encoding: "utf8"
});

let dashboardSyntaxError = null;
try {
  const start = dashboard.lastIndexOf("<script>");
  const end = dashboard.lastIndexOf("</script>");
  if (start === -1 || end === -1 || end <= start) {
    throw new Error("inline Chronicle script block not found");
  }
  new vm.Script(dashboard.slice(start + "<script>".length, end));
} catch (error) {
  dashboardSyntaxError = error;
}

const markersOk =
  server.includes(requireLine) &&
  server.includes(toolMarker) &&
  server.includes(helperMarker) &&
  server.includes(runToolMarker) &&
  server.includes(routeMarker) &&
  dashboard.includes(scribePanelMarker) &&
  dashboard.includes(loadScribeMarker) &&
  dashboard.includes(precedenceNew) &&
  dashboard.includes("await loadScribe();$('lastSync')");

if (serverCheck.status !== 0 || dashboardSyntaxError || !markersOk) {
  fs.writeFileSync(serverPath, originalServer, "utf8");
  fs.writeFileSync(dashboardPath, originalDashboard, "utf8");
  console.error("Chronicle Scribe integration failed; original files restored.");
  if (serverCheck.status !== 0) {
    console.error(serverCheck.stderr || serverCheck.stdout || "Unknown server syntax error");
  }
  if (dashboardSyntaxError) {
    console.error(dashboardSyntaxError.stack || dashboardSyntaxError.message);
  }
  process.exit(1);
}

if (server === originalServer && dashboard === originalDashboard) {
  console.log("Chronicle Scribe integration already enabled.");
} else {
  console.log("Chronicle Scribe live-evidence layer enabled and syntax-validated.");
}
