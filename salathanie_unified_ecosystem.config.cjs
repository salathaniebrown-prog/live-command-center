module.exports = {
  "apps": [
    {
      "name": "astra-8088-dashboard_server",
      "script": "/data/data/com.termux/files/home/dashboard_server.py",
      "interpreter": "python3",
      "cwd": "/data/data/com.termux/files/home",
      "max_memory_restart": "48M",
      "autorestart": true,
      "max_restarts": 5,
      "min_uptime": "10s",
      "restart_delay": 2000
    },
    {
      "name": "salathanie-gw-8090",
      "script": "/data/data/com.termux/files/home/live-command-center/alstra_unified_8090_gateway.py",
      "interpreter": "python3",
      "cwd": "/data/data/com.termux/files/home/live-command-center",
      "max_memory_restart": "48M",
      "autorestart": true,
      "max_restarts": 5,
      "min_uptime": "10s",
      "restart_delay": 2000
    },
    {
      "name": "salathanie-avatar-car-hub",
      "script": "/data/data/com.termux/files/home/live-command-center/avatar_car_hub.py",
      "interpreter": "python3",
      "cwd": "/data/data/com.termux/files/home/live-command-center",
      "max_memory_restart": "48M",
      "autorestart": true,
      "max_restarts": 5,
      "min_uptime": "10s",
      "restart_delay": 2000
    },
    {
      "name": "salathanie-pilot",
      "script": "/data/data/com.termux/files/home/live-command-center/universal_pilot.py",
      "interpreter": "python3",
      "cwd": "/data/data/com.termux/files/home/live-command-center",
      "max_memory_restart": "48M",
      "autorestart": true,
      "max_restarts": 5,
      "min_uptime": "10s",
      "restart_delay": 2000
    },
    {
      "name": "salathanie-car-bridge",
      "script": "/data/data/com.termux/files/home/live-command-center/car_port_bridge.py",
      "interpreter": "python3",
      "cwd": "/data/data/com.termux/files/home/live-command-center",
      "max_memory_restart": "48M",
      "autorestart": true,
      "max_restarts": 5,
      "min_uptime": "10s",
      "restart_delay": 2000
    },
    {
      "name": "salathanie-szero-evtol",
      "script": "/data/data/com.termux/files/home/live-command-center/szero_plus_evtol_telemetry.py",
      "interpreter": "python3",
      "cwd": "/data/data/com.termux/files/home/live-command-center",
      "max_memory_restart": "48M",
      "autorestart": true,
      "max_restarts": 5,
      "min_uptime": "10s",
      "restart_delay": 2000,
      "args": "--daemon"
    },
    {
      "name": "salathanie-ram-watch",
      "script": "/data/data/com.termux/files/home/live-command-center/ram_watchdog_telemetry.py",
      "interpreter": "python3",
      "cwd": "/data/data/com.termux/files/home/live-command-center",
      "max_memory_restart": "48M",
      "autorestart": true,
      "max_restarts": 5,
      "min_uptime": "10s",
      "restart_delay": 2000
    },
    {
      "name": "salathanie-jet-hud",
      "script": "/data/data/com.termux/files/home/live-command-center/astra_jet_hud.py",
      "interpreter": "python3",
      "cwd": "/data/data/com.termux/files/home/live-command-center",
      "max_memory_restart": "48M",
      "autorestart": true,
      "max_restarts": 5,
      "min_uptime": "10s",
      "restart_delay": 2000
    }
  ]
};
