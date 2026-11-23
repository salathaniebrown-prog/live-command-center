#!/usr/bin/env python3
"""
SalathanieAI — Unified Multi-Folder Startup Profile Builder
Reads master_ecosystem_map.json + live PM2 paths to create:
  1. salathanie_unified_ecosystem.config.cjs (RAM-safe Always-On Core Tier)
  2. salathanie_ondemand_registry.json       (All folders, HTML HUDs & wakeable services)
Strictly additive: never modifies or deletes any existing project files.
"""
import json
import subprocess
from pathlib import Path

HOME = Path.home()
REPO = HOME / "live-command-center"
MAP_FILE = REPO / "master_ecosystem_map.json"
ECOSYSTEM_CJS = REPO / "salathanie_unified_ecosystem.config.cjs"
REGISTRY_JSON = REPO / "salathanie_ondemand_registry.json"

CORE_SPECS = [
    ("astra-8088-dashboard_server", str(HOME / "dashboard_server.py"), "", "96M"),
    ("salathanie-gw-8090", str(REPO / "alstra_unified_8090_gateway.py"), "", "64M"),
    ("salathanie-avatar-car-hub", str(REPO / "avatar_car_hub.py"), "", "64M"),
    ("salathanie-pilot", str(REPO / "universal_pilot.py"), "", "64M"),
    ("salathanie-car-bridge", str(REPO / "car_port_bridge.py"), "", "80M"),
    ("salathanie-szero-evtol", str(REPO / "szero_plus_evtol_telemetry.py"), "--daemon", "64M"),
    ("salathanie-ram-watch", str(REPO / "ram_watchdog_telemetry.py"), "", "48M"),
    ("salathanie-jet-hud", None, "", "64M"),
]


def _ensure_map() -> dict:
    if MAP_FILE.exists():
        try:
            return json.loads(MAP_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    skip = {".cache", ".npm", ".pm2", ".cargo", ".local", ".termux", "storage", "node_modules", "__pycache__", ".git"}
    dirs = []
    for p in sorted(HOME.iterdir()):
        if p.is_dir() and p.name not in skip and not p.name.startswith("."):
            dirs.append({
                "folder": str(p),
                "py_count": len(list(p.glob("*.py"))),
                "html_count": len(list(p.glob("*.html"))),
                "db_count": len(list(p.glob("*.db"))),
            })
    data = {"home_root": {"py": [f.name for f in HOME.glob("*.py")], "html": [f.name for f in HOME.glob("*.html")]}, "project_folders": dirs}
    MAP_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return data


def _live_pm2_paths() -> dict:
    out = {}
    try:
        r = subprocess.run(["pm2", "jlist"], capture_output=True, text=True, timeout=6)
        if r.returncode == 0 and r.stdout.strip().startswith("["):
            for p in json.loads(r.stdout):
                env = p.get("pm2_env") or {}
                nm = p.get("name")
                sp = env.get("pm_exec_path")
                if nm and sp:
                    args = env.get("args") or []
                    out[nm] = {"script": sp, "args": " ".join(args) if isinstance(args, list) else str(args)}
    except Exception:
        pass
    return out


def build() -> dict:
    eco_map = _ensure_map()
    live = _live_pm2_paths()

    # 1. Build RAM-safe Always-On Core Tier
    core_apps = []
    core_scripts = set()
    for name, fallback_script, default_args, mem_cap in CORE_SPECS:
        script = live.get(name, {}).get("script") or fallback_script
        args = live.get(name, {}).get("args") or default_args
        if script and Path(script).exists():
            app = {
                "name": name,
                "script": script,
                "interpreter": "python3",
                "cwd": str(Path(script).parent),
                "max_memory_restart": mem_cap,
                "autorestart": True,
                "max_restarts": 5,
                "min_uptime": "10s",
                "restart_delay": 2000,
            }
            if args:
                app["args"] = args
            core_apps.append(app)
            core_scripts.add(str(Path(script).resolve()))

    cjs_content = "module.exports = " + json.dumps({"apps": core_apps}, indent=2) + ";\n"
    ECOSYSTEM_CJS.write_text(cjs_content, encoding="utf-8")

    # 2. Index every folder from master_ecosystem_map.json for Zero-RAM Vault + On-Demand Wake
    folders_index = []
    ondemand_services = []
    scan_roots = [HOME] + [Path(d["folder"]) for d in eco_map.get("project_folders", []) if Path(d["folder"]).exists()]

    seen_roots = set()
    for root in scan_roots:
        r_res = str(root.resolve())
        if r_res in seen_roots:
            continue
        seen_roots.add(r_res)
        rel_folder = "__home__" if root == HOME else root.name
        htmls = sorted([f.name for f in root.glob("*.html")])
        pys = sorted([f for f in root.glob("*.py") if not f.name.startswith("_")])
        dbs = sorted([f.name for f in root.glob("*.db")])

        # Also check verified_source if present inside live-command-center
        vs_dir = root / "ALSTRA_VERIFIED_EVIDENCE_BUNDLE" / "verified_source"
        if vs_dir.exists():
            for vf in sorted(vs_dir.glob("*.py")):
                if any(k in vf.name.lower() for k in ("8159", "8151", "dashboard", "3000", "hud")):
                    pys.append(vf)

        if not htmls and not pys and not dbs:
            continue

        folder_services = []
        for pf in pys:
            pres = str(pf.resolve())
            if pres in core_scripts:
                continue
            # Identify likely runnable server/agent scripts
            try:
                head = pf.read_text(encoding="utf-8", errors="ignore")[:3500]
            except Exception:
                head = ""
            is_runnable = any(tok in head for tok in ("serve_forever", "uvicorn", "FastAPI", "Flask", "ThreadingHTTPServer", "HTTPServer", "while not _STOP", "asyncio.run"))
            if is_runnable:
                svc_name = f"eco-{rel_folder[:10]}-{pf.stem[:20]}".lower().replace("_", "-")
                entry = {
                    "name": svc_name,
                    "folder": rel_folder,
                    "file": pf.name,
                    "script": pres,
                    "cwd": str(pf.parent),
                    "max_memory_restart": "64M",
                }
                folder_services.append(entry)
                ondemand_services.append(entry)

        folders_index.append({
            "folder": rel_folder,
            "path": r_res,
            "html_files": htmls,
            "db_files": dbs,
            "services": folder_services,
        })

    registry = {
        "core_count": len(core_apps),
        "core_names": [a["name"] for a in core_apps],
        "folders": folders_index,
        "ondemand_services": ondemand_services,
    }
    REGISTRY_JSON.write_text(json.dumps(registry, indent=2), encoding="utf-8")
    return registry


if __name__ == "__main__":
    reg = build()
    print(f"[OK] Core Tier Apps ({reg['core_count']}): {', '.join(reg['core_names'])}")
    print(f"[OK] Linked Folders ({len(reg['folders'])}) | On-Demand Services ({len(reg['ondemand_services'])})")
    for f in reg["folders"]:
        print(f"  - {f['folder']:<24} html:{len(f['html_files']):<3} db:{len(f['db_files']):<3} wakeable:{len(f['services'])}")
