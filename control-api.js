const { execSync } = require("child_process");
const ADMIN_TOK = process.env.ASTRA_ADMIN_TOKEN || "";
const fs = require("fs");

const state = { model: "GPT-5.2-TURBO", agents: ["SEC-AUDITOR", "HPC-SCHEDULER"], temp: 0.7 };

function runCmd(cmd) {
  try { return execSync(cmd, { timeout: 4000, encoding: "utf8" }).trim(); }
  catch (e) { return (e.stdout || e.stderr || e.message).toString().trim(); }
}

module.exports = function handleControl(req, res) {
  if (ADMIN_TOK && req.headers["x-astra-token"] !== ADMIN_TOK) { res.writeHead(401); return res.end(JSON.stringify({ok:false, output:"UNAUTHORIZED: Enter Admin Token"})); }
  let body = "";
  req.on("data", c => body += c);
  req.on("end", () => {
    const p = JSON.parse(body || "{}");
    let out = "OK";

    if (p.action === "infer") {
      const apiUrl = process.env.ASTRA_API_URL || "http://127.0.0";
      const apiKey = process.env.ASTRA_API_KEY || "ollama";
      const telem = fs.existsSync("telemetry_spine.jsonl")
        ? fs.readFileSync("telemetry_spine.jsonl", "utf8").trim().split("\n").slice(-3).join(" | ")
        : "No telemetry yet";
      const sysPrompt = "You are ASTRA Enterprise Core AI. Active model: " + (p.model || state.model) +
        ". Live hardware telemetry: " + telem;

      fetch(apiUrl, {
        method: "POST",
        headers: { "Content-Type": "application/json", "Authorization": "Bearer " + apiKey },
        body: JSON.stringify({
          model: p.endpointModel || process.env.ASTRA_MODEL || "deepseek-chat",
          temperature: Number(p.temp ?? state.temp),
          messages: [
            { role: "system", content: sysPrompt },
            { role: "user", content: p.prompt || "Status report." }
          ]
        })
      })
      .then(r => r.json())
      .then(d => {
        const reply = d.choices?.[0]?.message?.content || d.response || JSON.stringify(d);
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ ok: true, output: reply }));
      })
      .catch(err => {
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({
          ok: false,
          output: "[LOCAL / OFFLINE FALLBACK :: " + (p.model || state.model) + "]\n" +
                  "No inference server reachable at " + apiUrl + ".\n" +
                  "To connect live AI: start Ollama ('ollama serve') OR run:\n" +
                  "export ASTRA_API_URL='https://openai.com'\n" +
                  "export ASTRA_API_KEY='your-key' && ./start-spine.sh\n\n" +
                  "Telemetry Snapshot Analyzed:\n" + telem
        }));
      });
      return;
    }

    if (p.action === "shell") out = runCmd(p.cmd || "uptime");
    else if (p.action === "sys_diag") out = runCmd("uname -a && uptime && df -h . | tail -1");
    else if (p.action === "ps_list") out = runCmd("ps -ef | grep -E 'node|python|java' | grep -v grep");
    else if (p.action === "net_ports") out = runCmd("ss -tuln 2>/dev/null || netstat -tuln 2>/dev/null || ip addr show wlan0");
    else if (p.action === "rotate_logs") out = runCmd("gzip -f *.log 2>/dev/null; truncate -s 0 telemetry_spine.jsonl && echo 'Ring buffer purged & rotated'");
    else if (p.action === "restart_workers") out = runCmd("pkill -f 'python_worker.py|SpineLogger'; nohup python3 python_worker.py >/dev/null 2>&1 & nohup java SpineLogger >/dev/null 2>&1 & echo 'HPC Workers restarted'");
    else if (p.action === "switch_model") { state.model = p.model; out = "Active model -> " + state.model; }
    else if (p.action === "toggle_agent") { out = "Agent updated -> " + p.model; }
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ ok: true, action: p.action, output: out, state }));
  });
};
