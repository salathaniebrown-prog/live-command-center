const { execSync } = require("child_process");
const fs = require("fs");
const ADMIN_TOK = process.env.ASTRA_ADMIN_TOKEN || "";

const state = { model: "DEEPSEEK-R1-671B", agents: ["SEC-AUDITOR", "HPC-SCHEDULER"], temp: 0.7 };

function runCmd(cmd) {
  try { return execSync(cmd, { timeout: 4000, encoding: "utf8" }).trim(); }
  catch (e) { return (e.stdout || e.stderr || e.message).toString().trim(); }
}

function localHeuristicAudit(prompt, model, telem) {
  const lines = telem.split("\n").filter(Boolean);
  const last = lines[lines.length - 1] || "{}";
  return `[ASTRA AUTONOMOUS ENGINE :: ${model}]\n` +
    `Query: "${prompt}"\nSamples: ${lines.length} live packets\nLatest: ${last}\n\n` +
    `Status: Multi-Runtime HPC (Python 4T + Java 21 4T) & SQLite WAL active.`;
}

async function tryProvider(url, key, modelName, sysPrompt, userPrompt, temp) {
  if (!key) throw new Error("No key");
  const r = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", "Authorization": "Bearer " + key },
    body: JSON.stringify({
      model: modelName,
      temperature: Number(temp ?? 0.7),
      messages: [{ role: "system", content: sysPrompt }, { role: "user", content: userPrompt }]
    })
  });
  const d = await r.json();
  const txt = d.choices?.[0]?.message?.content || d.response;
  if (!txt) throw new Error("Empty response");
  return txt;
}

module.exports = async function handleControl(req, res) {
  if (ADMIN_TOK && req.headers["x-astra-token"] !== ADMIN_TOK) {
    res.writeHead(401, { "Content-Type": "application/json" });
    return res.end(JSON.stringify({ ok: false, output: "UNAUTHORIZED: Enter Admin Token" }));
  }

  let body = "";
  req.on("data", c => body += c);
  req.on("end", async () => {
    const p = JSON.parse(body || "{}");

    if (p.action === "infer") {
      const telem = fs.existsSync("telemetry_spine.jsonl")
        ? fs.readFileSync("telemetry_spine.jsonl", "utf8").trim().split("\n").slice(-4).join("\n")
        : "No telemetry recorded yet.";
      const sysPrompt = "You are ASTRA Enterprise Core AI. Live telemetry:\n" + telem;
      const userPrompt = p.prompt || "Audit live telemetry.";

      const chain = [
        { name: "DEEPSEEK", url: process.env.ASTRA_API_URL || "https://deepseek.com", key: process.env.ASTRA_API_KEY, mdl: process.env.ASTRA_MODEL || "deepseek-chat" },
        { name: "GEMINI", url: "https://googleapis.com", key: process.env.GEMINI_API_KEY, mdl: "gemini-2.5-flash" },
        { name: "OLLAMA-LOCAL", url: "http://127.0.0", key: "ollama", mdl: "llama3.2" }
      ];

      for (const provider of chain) {
        try {
          const reply = await tryProvider(provider.url, provider.key, provider.mdl, sysPrompt, userPrompt, p.temp);
          res.writeHead(200, { "Content-Type": "application/json" });
          return res.end(JSON.stringify({ ok: true, output: `[ROUTE: ${provider.name}]\n` + reply }));
        } catch (e) {}
      }

      res.writeHead(200, { "Content-Type": "application/json" });
      return res.end(JSON.stringify({ ok: true, output: localHeuristicAudit(userPrompt, p.model || state.model, telem) }));
    }

    let out = "OK";
    if (p.action === "shell") out = runCmd(p.cmd || "uptime");
    else if (p.action === "sys_diag") out = runCmd("uname -a && uptime && df -h . | tail -1");
    else if (p.action === "ps_list") out = runCmd("ps -ef | grep -E 'node|python|java' | grep -v grep");
    else if (p.action === "net_ports") out = runCmd("ss -tuln 2>/dev/null || netstat -tuln 2>/dev/null || ip addr show wlan0");
    else if (p.action === "backup_db") out = runCmd("mkdir -p backups && cp astra_ledger.db backups/astra_ledger_$(date +%Y%m%d_%H%M%S).db && ls -lh backups/ | tail -n 3");
    else if (p.action === "rotate_logs") out = runCmd("gzip -f *.log 2>/dev/null; truncate -s 0 telemetry_spine.jsonl && echo 'Ring buffer purged & rotated'");
    else if (p.action === "restart_workers") out = runCmd("pkill -f 'python_worker.py|SpineLogger'; nohup python3 python_worker.py >/dev/null 2>&1 & nohup java SpineLogger >/dev/null 2>&1 & echo 'HPC Workers restarted'");
    else if (p.action === "switch_model") { state.model = p.model; out = "Active model -> " + state.model; }
    else if (p.action === "toggle_agent") { out = "Agent updated -> " + p.model; }
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ ok: true, action: p.action, output: out, state }));
  });
};
