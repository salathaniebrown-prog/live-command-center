# ASTRA ENTERPRISE CORE :: SYSTEM BLUEPRINT
- **Repo:** `salathaniebrown-prog/live-command-center` (`~/astra-enterprise-core`)
- **Start Stack:** `./start-spine.sh` (loads `.env`, starts Node `web-dashboard.js` on `:8080`, `python_worker.py` 4T HPC + thermal guardrail + ETH mempool, `global-telemetry.py` USGS/NWS/NASA + hourly SQLite backup, and `SpineLogger.java` 4T JVM21)
- **Key Routes:** `/` (`dashboard.html`), `/api/telemetry`, `/api/ledger` (`astra_ledger.db`), `/api/control` (protected by `x-astra-token` / `ASTRA_ADMIN_TOKEN`), `/api/export`, `/api/health`
- **Remote Access:** `cloudflared tunnel --url http://127.0.0.1:8080`
- **Optional Report Hook:** Set `ASTRA_REPORT_WEBHOOK=https://...` in `.env` for hourly backup summaries.
