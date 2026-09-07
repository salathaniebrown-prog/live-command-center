"use strict";

const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const target = path.join(__dirname, "..", "server.js");
const original = fs.readFileSync(target, "utf8");
let next = original;

const requireLine =
  'const { assertObservationToolset } = require("./command-policy");';

if (!next.includes(requireLine)) {
  const anchor = '"use strict";\n\n';
  if (!next.startsWith(anchor)) {
    throw new Error("Observation gate patch refused: server preamble anchor not found");
  }
  next = next.replace(anchor, `${anchor}${requireLine}\n`);
}

const assertion = "assertObservationToolset(TOOLS);";
if (!next.includes(assertion)) {
  const aiAnchor = "];\n\nconst AI_TOOLS = [";
  const instructionAnchor = "];\n\nconst INSTRUCTIONS = [";

  if (next.includes(aiAnchor)) {
    next = next.replace(
      aiAnchor,
      `];\n\n${assertion}\n\nconst AI_TOOLS = [`
    );
  } else if (next.includes(instructionAnchor)) {
    next = next.replace(
      instructionAnchor,
      `];\n\n${assertion}\n\nconst INSTRUCTIONS = [`
    );
  } else {
    throw new Error("Observation gate patch refused: toolset boundary anchor not found");
  }
}

if (next === original) {
  console.log("Eagle Eyes observation gate already enforced.");
  process.exit(0);
}

fs.writeFileSync(target, next, "utf8");

const check = spawnSync(process.execPath, ["--check", target], {
  encoding: "utf8"
});

if (check.status !== 0) {
  fs.writeFileSync(target, original, "utf8");
  console.error("Observation gate validation failed; original server.js restored.");
  console.error(check.stderr || check.stdout || "Unknown syntax error");
  process.exit(1);
}

console.log("Eagle Eyes observation gate injected and syntax-validated.");
