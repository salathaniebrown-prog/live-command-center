"use strict";

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const target = path.join(__dirname, "..", "server.js");
const original = fs.readFileSync(target, "utf8");

const signatureOld = "async function freeCommand(message) {";
const signatureNew = "async function freeCommand(message, forceFree = false) {";
const emptyAnchor = [
  "  if (!q) {",
  "    return null;",
  "  }",
  "",
].join("\n");
const aiFirstGuard = [
  "  // AI-first: when GPT is configured, let the model choose live tools.",
  "  // forceFree is reserved for graceful fallback after an AI failure.",
  "  if (OPENAI_API_KEY && !forceFree) {",
  "    return null;",
  "  }",
  "",
].join("\n");

let next = original;

if (!next.includes(signatureNew)) {
  if (!next.includes(signatureOld)) {
    throw new Error("AI-first patch refused: freeCommand signature anchor not found");
  }
  next = next.replace(signatureOld, signatureNew);
}

if (!next.includes("if (OPENAI_API_KEY && !forceFree)")) {
  const functionStart = next.indexOf(signatureNew);
  const anchorAt = next.indexOf(emptyAnchor, functionStart);

  if (anchorAt === -1) {
    throw new Error("AI-first patch refused: freeCommand empty-message anchor not found");
  }

  const insertAt = anchorAt + emptyAnchor.length;
  next = next.slice(0, insertAt) + aiFirstGuard + next.slice(insertAt);
}

// If GPT is configured but the API call fails, fall back to the existing
// read-only command engine whenever it can answer the request.
const assistantRoute = 'app.post(\n  "/api/assistant",';
const streamRoute = 'app.post(\n  "/api/assistant/stream",';

function insertFallback(routeAnchor, catchAnchor, fallbackCode, marker) {
  if (next.includes(marker)) return;

  const routeAt = next.indexOf(routeAnchor);
  if (routeAt === -1) {
    throw new Error(`AI-first patch refused: route anchor not found: ${routeAnchor}`);
  }

  const catchAt = next.indexOf(catchAnchor, routeAt);
  if (catchAt === -1) {
    throw new Error(`AI-first patch refused: catch anchor not found after ${routeAnchor}`);
  }

  const insertAt = catchAt + catchAnchor.length;
  next = next.slice(0, insertAt) + fallbackCode + next.slice(insertAt);
}

insertFallback(
  assistantRoute,
  "    } catch (e) {\n",
  [
    "      // AI-FIRST-FALLBACK: preserve live functionality if GPT is unavailable.",
    "      const fallback = await freeCommand(message, true);",
    "      if (fallback) {",
    "        return res.json({",
    "          ok: true,",
    "          mode: \"free-fallback\",",
    "          model: \"free-command-mode\",",
    "          tool: fallback.tool,",
    "          text: fallback.text,",
    "          aiUnavailable: true",
    "        });",
    "      }",
    "",
  ].join("\n") + "\n",
  "AI-FIRST-FALLBACK: preserve live functionality if GPT is unavailable."
);

insertFallback(
  streamRoute,
  "    } catch (e) {\n",
  [
    "      // AI-FIRST-STREAM-FALLBACK: keep the command rail useful if GPT fails.",
    "      if (!controller.signal.aborted) {",
    "        const fallback = await freeCommand(message, true);",
    "        if (fallback) {",
    "          sendSSE(res, \"fallback\", {",
    "            mode: \"free-fallback\",",
    "            tool: fallback.tool",
    "          });",
    "          sendSSE(res, \"delta\", { text: fallback.text });",
    "          sendSSE(res, \"done\", {",
    "            model: \"free-command-mode\",",
    "            mode: \"free-fallback\"",
    "          });",
    "          return;",
    "        }",
    "      }",
    "",
  ].join("\n") + "\n",
  "AI-FIRST-STREAM-FALLBACK: keep the command rail useful if GPT fails."
);

// Add OpenAI's hosted web-search tool alongside Eagle Eyes' read-only
// function tools. This does not replace the dedicated NWS/USGS/EONET,
// Open-Meteo, CelesTrak, or PX4 sources.
const toolsEndAnchor = "];\n\nconst INSTRUCTIONS = [";
const hostedToolsBlock = [
  "];",
  "",
  "const AI_TOOLS = [",
  "  { type: \"web_search\" },",
  "  ...TOOLS",
  "];",
  "",
  "const INSTRUCTIONS = ["
].join("\n");

if (!next.includes("const AI_TOOLS = [")) {
  if (!next.includes(toolsEndAnchor)) {
    throw new Error("Web-search patch refused: tool-array anchor not found");
  }
  next = next.replace(toolsEndAnchor, hostedToolsBlock);
}

const instructionAnchor =
  '  "For general factual questions that benefit from reference knowledge, call search_world_knowledge. For current weather by place, call get_global_weather.",';

const webInstruction =
  '  "Use the hosted web_search tool for current, recent, or internet-specific questions that are not fully answered by the dedicated Eagle Eyes live feeds. Prefer the dedicated live feeds for NWS, USGS, NASA EONET, Open-Meteo weather, CelesTrak satellites, and PX4 telemetry.",';

if (!next.includes("Use the hosted web_search tool for current, recent")) {
  if (!next.includes(instructionAnchor)) {
    throw new Error("Web-search patch refused: instruction anchor not found");
  }
  next = next.replace(
    instructionAnchor,
    instructionAnchor + "\n" + webInstruction
  );
}

if (next.includes("tools: TOOLS,")) {
  next = next.replace("tools: TOOLS,", "tools: AI_TOOLS,");
}

if (next.includes("tools:\n            TOOLS,")) {
  next = next.replace(
    "tools:\n            TOOLS,",
    "tools:\n            AI_TOOLS,"
  );
}

const statusAnchor = [
  "      readOnlyTools:",
  "        TOOLS.map(",
  "          (t) =>",
  "            t.name",
  "        ),"
].join("\n");

const statusWithWeb = [
  "      hostedTools:",
  "        OPENAI_API_KEY",
  "          ? [\"web_search\"]",
  "          : [],",
  "",
  "      webSearch:",
  "        Boolean(",
  "          OPENAI_API_KEY",
  "        ),",
  "",
  statusAnchor
].join("\n");

if (!next.includes("      hostedTools:")) {
  if (!next.includes(statusAnchor)) {
    throw new Error("Web-search patch refused: assistant-status anchor not found");
  }
  next = next.replace(statusAnchor, statusWithWeb);
}

if (next === original) {
  console.log("Eagle Eyes AI-first routing and web search already enabled.");
  process.exit(0);
}

fs.writeFileSync(target, next, "utf8");

const check = spawnSync(process.execPath, ["--check", target], {
  encoding: "utf8"
});

if (check.status !== 0) {
  fs.writeFileSync(target, original, "utf8");
  console.error("AI-first/web-search patch validation failed; original server.js restored.");
  console.error(check.stderr || check.stdout || "Unknown syntax error");
  // Keep the service bootable with the known-good server instead of taking it down.
  process.exit(0);
}

console.log("Eagle Eyes AI-first routing + OpenAI web search enabled and syntax-validated.");
