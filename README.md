# Live Command Center

This package turns the supplied command-center photo into a live web dashboard.

## Important
The included values are DEMO values. They are not measurements from the pictured computer or supercomputers.

## Run
1. Install Node.js 18+.
2. Open a terminal in this folder.
3. Run:
   ```
   npm install
   npm start
   ```
4. Open http://localhost:3000

The browser polls these endpoints every 2 seconds:
- GET /api/status
- GET /api/metrics
- GET /api/workloads
- GET /api/deployment
- GET /api/health

## Connect real hardware/services
Set STATUS_URL, METRICS_URL, WORKLOADS_URL and DEPLOYMENT_URL to your real JSON API endpoints. The server acts as a small adapter/proxy, so API credentials can stay on the server rather than in browser JavaScript.

Your upstream APIs should return JSON such as:

**metrics:**
```json
{"cpu":72,"gpu":94,"memory":81,"storage":66,"temperatureC":58}
```

**deployment:**
```json
{"progress":100,"stage":"LIVE","success":true}
```

**status:**
```json
{"online":true,"systemStatus":"OPTIMAL","mode":"LIVE"}
```

**workloads:**
```json
["AI model training","Physics simulation","Digital twins"]
```
