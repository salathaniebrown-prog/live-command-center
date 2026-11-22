module.exports = {
  apps: [
    {
      name: "salathanie-wal-8182",
      script: "/data/data/com.termux/files/home/live-command-center/astra_svc_8182.py",
      interpreter: "python3",
      max_restarts: 5,
      min_uptime: "10s",
      restart_delay: 5000,
      max_memory_restart: "64M",
      env: { ASTRA_HOST: "0.0.0.0", ASTRA_LOCATION: "Greensboro, NC" }
    },
    {
      name: "salathanie-causal-shadow",
      script: "/data/data/com.termux/files/home/live-command-center/causal_shadow.py",
      interpreter: "python3",
      max_restarts: 5,
      min_uptime: "10s",
      restart_delay: 5000,
      max_memory_restart: "64M"
    },
    {
      name: "salathanie-pilot",
      script: "/data/data/com.termux/files/home/live-command-center/universal_pilot.py",
      interpreter: "python3",
      max_restarts: 5,
      min_uptime: "10s",
      restart_delay: 5000,
      max_memory_restart: "64M"
    },
    {
      name: "salathanie-trinity",
      script: "/data/data/com.termux/files/home/live-command-center/trinity_core.py",
      interpreter: "python3",
      max_restarts: 5,
      min_uptime: "10s",
      restart_delay: 5000,
      max_memory_restart: "64M"
    },
    {
      name: "salathanie-agents",
      script: "/data/data/com.termux/files/home/live-command-center/salathanie_agents.py",
      interpreter: "python3",
      max_restarts: 5,
      min_uptime: "10s",
      restart_delay: 5000,
      max_memory_restart: "64M"
    },
    {
      name: "salathanie-tunnel",
      script: "cloudflared",
      args: "tunnel --no-autoupdate --url http://127.0.0.1:8125",
      max_restarts: 5,
      min_uptime: "10s",
      restart_delay: 8000,
      max_memory_restart: "80M"
    }
  ]
};
