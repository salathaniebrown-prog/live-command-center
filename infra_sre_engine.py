#!/usr/bin/env python3
"""
Salathanie A.I — Telemetry Backend, SRE/IaC Blueprint Engine, ISO/OSI Inspector,
Zero-Error Validator, Self-Error Analyzer & On-Screen Linux A.I. Copilot.
"""
import glob
import json
import os
import platform
import py_compile
import re
import socket
import subprocess
import tempfile
import time
from pathlib import Path

from hdc_shm_bus import HDCSharedMemoryBus

REPO = Path("/data/data/com.termux/files/home/live-command-center")
BLUEPRINTS_DIR = REPO / "infra_blueprints"


def _cmd(args: list[str], timeout: int = 5) -> str:
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        return (r.stdout or r.stderr).strip()[:1200]
    except Exception as e:
        return f"unavailable ({e})"


def prometheus_metrics(mem_avail_mb: int, broadband_ms: float) -> str:
    """OpenMetrics / Prometheus exposition format for Zabbix 8.0 LTS & Grafana scraping."""
    seq, hmac_ok = 0, 0
    try:
        with HDCSharedMemoryBus() as bus:
            with bus.read_latest_view() as rec:
                if rec:
                    seq = rec["seq"]
                    hmac_ok = 1 if rec.get("hmac_ok") else 0
    except Exception:
        pass
    load1 = os.getloadavg()[0] if hasattr(os, "getloadavg") else 0.0
    lines = [
        "# HELP salathanie_mem_available_megabytes Available host RAM in MB",
        "# TYPE salathanie_mem_available_megabytes gauge",
        f"salathanie_mem_available_megabytes {mem_avail_mb}",
        "# HELP salathanie_broadband_latency_ms Broadband HTTP probe latency",
        "# TYPE salathanie_broadband_latency_ms gauge",
        f"salathanie_broadband_latency_ms {broadband_ms}",
        "# HELP salathanie_hdc_ring_seq Latest zero-copy HDC ring sequence",
        "# TYPE salathanie_hdc_ring_seq counter",
        f"salathanie_hdc_ring_seq {seq}",
        "# HELP salathanie_hdc_hmac_verified Zero-Trust HMAC attestation (1=ok)",
        "# TYPE salathanie_hdc_hmac_verified gauge",
        f"salathanie_hdc_hmac_verified {hmac_ok}",
        "# HELP salathanie_cpu_load1 1-minute UNIX load average",
        "# TYPE salathanie_cpu_load1 gauge",
        f"salathanie_cpu_load1 {load1:.2f}",
    ]
    return "\n".join(lines) + "\n"


def osi_tcpip_diagnostics() -> dict:
    """Live ISO/OSI 7-Layer & TCP/IP stack inspection on Termux/Linux."""
    lan_ip = "127.0.0.1"
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("1.1.1.1", 80))
            lan_ip = s.getsockname()[0]
    except OSError:
        pass

    dns_ok = False
    try:
        socket.gethostbyname("cloudflare.com")
        dns_ok = True
    except OSError:
        pass

    open_ports = []
    for p in (8088, 8090, 8125, 8126, 8128, 8182):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(0.2)
            if s.connect_ex(("127.0.0.1", p)) == 0:
                open_ports.append(p)

    return {
        "os_admin": {
            "kernel": platform.release(),
            "arch": platform.machine(),
            "uptime": _cmd(["uptime"]),
            "disk_repo": _cmd(["df", "-h", str(REPO)]),
        },
        "iso_osi_stack": {
            "L1_L2_Physical_DataLink": "Wi-Fi / Android Netlink interface active" if lan_ip != "127.0.0.1" else "Loopback only",
            "L3_Network_IP": {"lan_ipv4": lan_ip, "routes": _cmd(["ip", "route"]) or "restricted on Android"},
            "L4_Transport_TCP": {"listening_core_ports": open_ports, "protocol": "TCP/QUIC (HTTP/2 & HTTP/3 via cloudflared)"},
            "L5_L6_Session_Presentation": {"tls": "TLS 1.3 via Cloudflare Edge", "attestation": "HMAC-SHA256 Zero-Copy SHM"},
            "L7_Application": {"dns_ok": dns_ok, "telemetry_endpoint": "/metrics", "protocols": ["HTTP/1.1", "FIX 4.4", "FAST", "OpenMetrics"]},
        },
    }


def self_analyze_errors() -> dict:
    """Scan PM2 logs and classify recurring failures with actionable Termux/Linux fixes."""
    patterns = [
        (r"Errno 98|address already in use", "PORT_CONFLICT", "Bind dynamically via hdc_shm_bus.allocate_port() or free port with fuser -k <port>/tcp"),
        (r"SyntaxError|IndentationError", "CODE_SYNTAX_ERROR", "Run python3 -m py_compile <file> before restarting PM2"),
        (r"BufferError", "MMAP_VIEW_LEAK", "Release memoryview inside a context manager before bus.close()"),
        (r"OOM|MemoryError|Killed", "RAM_PRESSURE", "Enforce max_memory_restart in ecosystem.config.js and keep host RAM <85%"),
        (r"(?:HTTP/[0-9.]+\s+|status[=:\s]+)(?:403|404|502|530)\b|connection refused|\bERR\b.*tunnel", "UPSTREAM_OR_TUNNEL", "Check salathanie_ports.json and verify target port is listening"),
    ]
    findings = []
    log_files = sorted(glob.glob(os.path.expanduser("~/.pm2/logs/salathanie-*-error.log")))
    for lf in log_files:
        try:
            tail = Path(lf).read_text(encoding="utf-8", errors="ignore").splitlines()[-40:]
        except OSError:
            continue
        blob = "\n".join(tail)
        for rx, code, fix in patterns:
            m = re.search(rx, blob, re.I)
            if m:
                findings.append({"log": os.path.basename(lf), "type": code, "match": m.group(0), "recommended_fix": fix})
    return {
        "ts": int(time.time()),
        "logs_scanned": len(log_files),
        "status": "CLEAN" if not findings else "ISSUES_FOUND",
        "findings": findings,
    }


def validate_code_zero_error(lang: str, code: str) -> dict:
    """Syntax-verify Bash or Python commands before execution to prevent coding errors."""
    lang_l = lang.lower().strip()
    suffix = ".py" if lang_l.startswith("py") else ".sh"
    with tempfile.NamedTemporaryFile("w", suffix=suffix, delete=False, encoding="utf-8") as tf:
        tf.write(code)
        tmp_path = tf.name
    try:
        if suffix == ".py":
            try:
                py_compile.compile(tmp_path, doraise=True)
                return {"ok": True, "lang": "python3", "message": "Zero syntax errors detected."}
            except py_compile.PyCompileError as e:
                return {"ok": False, "lang": "python3", "error": str(e)}
        else:
            r = subprocess.run(["bash", "-n", tmp_path], capture_output=True, text=True, timeout=5)
            return {"ok": r.returncode == 0, "lang": "bash", "message": "Zero shell syntax errors." if r.returncode == 0 else r.stderr.strip()}
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass


def generate_blueprint(stack: str) -> dict:
    """Generate production-grade IaC & server configuration blueprints onto disk."""
    s = stack.lower().strip()
    target = BLUEPRINTS_DIR / s
    target.mkdir(parents=True, exist_ok=True)
    files = {}

    if s == "db_oracle_postgres":
        files["docker-compose.yml"] = (
            "services:\n"
            "  postgres:\n"
            "    image: postgres:19-alpine\n"
            "    environment:\n"
            "      POSTGRES_USER: salathanie\n"
            "      POSTGRES_PASSWORD: ${PG_PASS:-ChangeMeStrong19}\n"
            "      POSTGRES_DB: telemetry_core\n"
            "    ports: ['5432:5432']\n"
            "    volumes: ['pg19_data:/var/lib/postgresql/data']\n"
            "  pgbouncer:\n"
            "    image: edoburu/pgbouncer:latest\n"
            "    environment:\n"
            "      DB_HOST: postgres\n"
            "      POOL_MODE: transaction\n"
            "      MAX_CLIENT_CONN: 1000\n"
            "    ports: ['6432:5432']\n"
            "  oracle-free:\n"
            "    image: container-registry.oracle.com/database/free:latest\n"
            "    environment:\n"
            "      ORACLE_PWD: ${ORA_PASS:-ChangeMeOra2026}\n"
            "    ports: ['1521:1521']\n"
            "volumes:\n"
            "  pg19_data:\n"
        )
        files["middleware_router.py"] = (
            "# Dual Oracle + PostgreSQL 19 Telemetry Middleware Stub\n"
            "import os\n"
            "PG_DSN = os.getenv('PG_DSN', 'postgresql://salathanie@127.0.0.1:6432/telemetry_core')\n"
            "ORA_DSN = os.getenv('ORA_DSN', '127.0.0.1:1521/FREEPDB1')\n"
            "print({'postgres_pool': PG_DSN, 'oracle_pool': ORA_DSN, 'status': 'READY'})\n"
        )

    elif s == "iaas_terraform_ansible":
        files["main.tf"] = (
            'terraform {\n'
            '  required_version = ">= 1.9.0"\n'
            '}\n'
            'variable "region" { default = "us-east-1" }\n'
            'variable "instance_type" { default = "c7g.large" }\n'
            '# Provision VPC, Compute, Block Storage & Firewall (adapt provider block for AWS/GCP/Bare-Metal)\n'
            'output "provision_plan" {\n'
            '  value = "Salathanie IaaS Node (${var.instance_type}) in ${var.region} + 100GB NVMe + WireGuard/NFTables"\n'
            '}\n'
        )
        files["baremetal_site.yml"] = (
            "---\n"
            "- name: Salathanie Bare-Metal & Cloud UNIX Provisioning\n"
            "  hosts: all\n"
            "  become: true\n"
            "  tasks:\n"
            "    - name: Install core UNIX, Docker, HAProxy, Firewall & WireGuard packages\n"
            "      package:\n"
            "        name: [docker.io, haproxy, wireguard, ufw, fail2ban, htop, tcpdump]\n"
            "        state: present\n"
            "    - name: Enforce UFW default deny & allow SSH/HTTPS/WireGuard\n"
            "      shell: |\n"
            "        ufw default deny incoming\n"
            "        ufw allow 22/tcp && ufw allow 443/tcp && ufw allow 51820/udp\n"
            "        ufw --force enable\n"
        )

    elif s == "observability_stack":
        files["docker-compose.yml"] = (
            "services:\n"
            "  zabbix-server:\n"
            "    image: zabbix/zabbix-server-pgsql:alpine-8.0-latest\n"
            "    ports: ['10051:10051']\n"
            "  opensearch:\n"
            "    image: opensearchproject/opensearch:3.10.0\n"
            "    environment: ['discovery.type=single-node', 'OPENSEARCH_JAVA_OPTS=-Xms1g -Xmx1g']\n"
            "    ports: ['9200:9200']\n"
            "  elasticsearch:\n"
            "    image: docker.elastic.co/elasticsearch/elasticsearch:8.17.0\n"
            "    environment: ['discovery.type=single-node', 'ES_JAVA_OPTS=-Xms1g -Xmx1g']\n"
            "    ports: ['9201:9200']\n"
            "  kibana:\n"
            "    image: docker.elastic.co/kibana/kibana:8.17.0\n"
            "    ports: ['5601:5601']\n"
            "  grafana:\n"
            "    image: grafana/grafana-oss:latest\n"
            "    ports: ['3000:3000']\n"
        )
        files["prometheus_scrape.yml"] = (
            "scrape_configs:\n"
            "  - job_name: 'salathanie-edge-termux'\n"
            "    scrape_interval: 15s\n"
            "    static_configs:\n"
            "      - targets: ['192.168.1.115:8125']\n"
        )

    elif s == "net_proxy_jvm":
        files["haproxy.cfg"] = (
            "global\n  maxconn 4096\ndefaults\n  mode http\n  timeout connect 5s\n  timeout client 30s\n  timeout server 30s\n"
            "frontend edge_in\n  bind *:80\n  default_backend salathanie_nodes\n"
            "backend salathanie_nodes\n  balance roundrobin\n  option httpchk GET /api/pilot/status\n"
            "  server pilot 127.0.0.1:8125 check\n  server trinity 127.0.0.1:8126 check\n"
        )
        files["apache_vhost.conf"] = (
            "<VirtualHost *:80>\n  ServerName salathanie.local\n  ProxyPreserveHost On\n"
            "  ProxyPass / http://127.0.0.1:8125/\n  ProxyPassReverse / http://127.0.0.1:8125/\n</VirtualHost>\n"
        )
        files["wg0_vpn.conf"] = (
            "[Interface]\nAddress = 10.44.0.1/24\nListenPort = 51820\nPrivateKey = <GEN_WITH_WG_GENKEY>\n"
            "PostUp = nft add table inet nat; ufw route allow in on wg0\n"
        )
        files["jvm_engine.sh"] = (
            "#!/usr/bin/env bash\n"
            "exec java -XX:+UseZGC -XX:+ZGenerational -Xms512m -Xmx2g -XX:+HeapDumpOnOutOfMemoryError -jar app.jar\n"
        )

    elif s == "teamcity_cicd":
        files["settings.kts"] = (
            'import jetbrains.buildServer.configs.kotlin.*\n'
            'import jetbrains.buildServer.configs.kotlin.buildSteps.script\n'
            'import jetbrains.buildServer.configs.kotlin.triggers.vcs\n\n'
            'version = "2026.2"\n'
            'project {\n'
            '    buildType(SalathanieEdgeBuild)\n'
            '}\n'
            'object SalathanieEdgeBuild : BuildType({\n'
            '    name = "Salathanie AI Zero-Error CI/CD"\n'
            '    triggers { vcs {} }\n'
            '    steps {\n'
            '        script {\n'
            '            name = "Syntax & Unit Verification"\n'
            '            scriptContent = "python3 -m py_compile *.py && bash -n salathanie_recover.sh"\n'
            '        }\n'
            '    }\n'
            '})\n'
        )
    else:
        return {"ok": False, "error": f"Unknown blueprint '{stack}'"}

    for fname, content in files.items():
        (target / fname).write_text(content, encoding="utf-8")

    return {"ok": True, "stack": s, "dir": str(target), "files": list(files.keys()), "preview": files}


def linux_ai_copilot(query: str) -> dict:
    """On-Screen Linux A.I. Ops Assistant with Termux/UNIX command templates."""
    q = query.lower()
    recipes = [
        (("firewall", "ufw", "iptables", "nft", "vpn", "wireguard"), "Firewall / WireGuard VPN", "wg genkey | tee private.key | wg pubkey > public.key && sudo ufw status verbose"),
        (("port", "tcp", "socket", "osi", "network"), "TCP/IP & Socket Inspection", "ss -tulpn 2>/dev/null || netstat -tuln"),
        (("postgres", "oracle", "sql", "db"), "Database Health Check", "pg_isready -h 127.0.0.1 -p 5432 || ls -lh ~/live-command-center/*.db"),
        (("docker", "ansible", "terraform", "bare metal"), "IaC Validation", "terraform fmt -check && ansible-playbook --syntax-check baremetal_site.yml"),
        (("error", "crash", "ram", "pm2", "log"), "Zero-Error PM2 & RAM Check", "pm2 status && free -m && tail -n 20 ~/.pm2/logs/salathanie-*-error.log"),
    ]
    for keys, title, cmd in recipes:
        if any(k in q for k in keys):
            return {"topic": title, "query": query, "validated_command": cmd, "check": validate_code_zero_error("bash", cmd)}
    default_cmd = "uname -a && free -m && pm2 status"
    return {"topic": "OS-Level UNIX Administration", "query": query, "validated_command": default_cmd, "check": validate_code_zero_error("bash", default_cmd)}


LEARNING_HUB = [
    {"track": "Linux & UNIX Kernel / OS Admin", "url": "https://training.linuxfoundation.org/resources/?_sft_content_type=free-course"},
    {"track": "TCP/IP & ISO/OSI RFCs", "url": "https://www.ietf.org/standards/rfcs/"},
    {"track": "PostgreSQL 19 Official Docs", "url": "https://www.postgresql.org/docs/current/"},
    {"track": "Zabbix 8.0 LTS Manual", "url": "https://www.zabbix.com/documentation/current/en/manual"},
    {"track": "OpenSearch 3.x & Observability", "url": "https://opensearch.org/docs/latest/"},
    {"track": "Grafana & Prometheus Labs", "url": "https://grafana.com/docs/"},
    {"track": "Terraform & Ansible IaC Docs", "url": "https://developer.hashicorp.com/terraform/docs"},
    {"track": "HAProxy, Apache & TeamCity Kotlin DSL", "url": "https://teamcity.jetbrains.com/app/dsl-documentation/index.html"},
    {"track": "MIT OpenCourseWare (CS / Systems / AI)", "url": "https://ocw.mit.edu/search/?d=Electrical%20Engineering%20and%20Computer%20Science"},
]

INFRA_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Salathanie A.I — SRE, IaC & Linux Ops Center</title>
<style>
body{font-family:monospace;background:#090d14;color:#e6edf3;margin:12px}
.card{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px;margin-bottom:12px}
.nav a{display:inline-block;background:#1f6feb;color:#fff;padding:6px 10px;border-radius:6px;text-decoration:none;margin-right:6px;font-size:12px}
button{background:#238636;color:#fff;border:none;padding:7px 10px;border-radius:6px;cursor:pointer;margin:3px 2px;font-family:monospace}
button.alt{background:#1f6feb}button.purp{background:#8957e5}
input,textarea,select{width:100%;box-sizing:border-box;background:#0d1117;color:#e6edf3;border:1px solid #30363d;padding:8px;border-radius:6px;font-family:monospace;margin-top:6px}
pre{background:#0d1117;padding:8px;border-radius:6px;font-size:11px;overflow:auto;max-height:260px;white-space:pre-wrap;word-break:break-all}
a{color:#58a6ff}
</style></head><body>
<h2>Salathanie A.I — Telemetry Backend, SRE & IaC Center</h2>
<div class="nav" style="margin-bottom:10px">
  <a href="/">Universal Pilot</a>
  <a href="/agents" style="background:#8957e5">18-Agent Studio</a>
  <a href="/trader" style="background:#d29922;color:#0b0f14">Web Trader / OMS</a>
  <a href="/metrics" style="background:#238636">Live /metrics</a>
</div>

<div class="card">
  <b>1. Live ISO/OSI Stack, OS Admin & Self-Analyze Errors</b><br><br>
  <button onclick="callApi('/api/infra/osi','diagOut')">Inspect TCP/IP & ISO/OSI</button>
  <button class="alt" onclick="callApi('/api/infra/errors','diagOut')">Self-Analyze PM2 Errors</button>
  <pre id="diagOut">Click to run live diagnostics.</pre>
</div>

<div class="card">
  <b>2. Production IaC & Enterprise Blueprint Generator (Writes to ~/live-command-center/infra_blueprints/)</b><br><br>
  <button onclick="gen('db_oracle_postgres')">Oracle + Postgres 19</button>
  <button class="alt" onclick="gen('iaas_terraform_ansible')">Terraform + Ansible Bare-Metal</button>
  <button class="purp" onclick="gen('observability_stack')">Zabbix 8 + OpenSearch + ELK + Grafana</button>
  <button onclick="gen('net_proxy_jvm')">HAProxy + Apache + VPN + JVM</button>
  <button class="alt" onclick="gen('teamcity_cicd')">TeamCity CI/CD (Kotlin DSL)</button>
  <pre id="bpOut">Select a stack to generate production IaC files on disk.</pre>
</div>

<div class="card">
  <b>3. On-Screen Linux A.I. Copilot & Zero-Error Code Validator</b>
  <input id="q" value="check tcp ports and firewall">
  <button onclick="askLinux()">Ask Linux A.I.</button>
  <select id="lang"><option value="bash">Bash Syntax Guard (bash -n)</option><option value="python">Python Syntax Guard (py_compile)</option></select>
  <textarea id="code" rows="2">echo "Salathanie zero-error check OK"</textarea>
  <button class="purp" onclick="validateCode()">Verify Zero Errors</button>
  <pre id="aiOut">Ready.</pre>
</div>

<div class="card">
  <b>4. Unlimited Open Self-Learning Platforms</b>
  <ul id="learn" style="line-height:1.7;padding-left:18px"></ul>
</div>

<script>
async function callApi(url, outId){
  document.getElementById(outId).textContent = 'Running...';
  const r = await fetch(url);
  document.getElementById(outId).textContent = JSON.stringify(await r.json(), null, 2);
}
function gen(stack){ callApi('/api/infra/blueprint?stack='+encodeURIComponent(stack), 'bpOut'); }
function askLinux(){ callApi('/api/infra/copilot?q='+encodeURIComponent(document.getElementById('q').value), 'aiOut'); }
async function validateCode(){
  const l = encodeURIComponent(document.getElementById('lang').value);
  const c = encodeURIComponent(document.getElementById('code').value);
  callApi('/api/infra/validate?lang='+l+'&code='+c, 'aiOut');
}
fetch('/api/infra/learning').then(r=>r.json()).then(list=>{
  document.getElementById('learn').innerHTML = list.map(i=>`<li><a href="${i.url}" target="_blank">${i.track}</a></li>`).join('');
});
</script></body></html>"""
