module.exports = {
  apps: [
    {
      name: "salathanie-ingress-8088",
      script: "/data/data/com.termux/files/home/live-command-center/nodes/astra_ingress_8088.py",
      interpreter: "python3",
      max_restarts: 5,
      min_uptime: "10s",
      restart_delay: 5000,
      max_memory_restart: "64M"
    },
    {
      name: "salathanie-gw-8090",
      script: "/data/data/com.termux/files/home/live-command-center/nodes/alstra_unified_8090_gateway.py",
      interpreter: "python3",
      max_restarts: 5,
      min_uptime: "10s",
      restart_delay: 5000,
      max_memory_restart: "64M"
    },
    {
      name: "salathanie-spatial-8151",
      script: "/data/data/com.termux/files/home/live-command-center/nodes/astra_spatial_3d_server_8151.py",
      interpreter: "python3",
      max_restarts: 5,
      min_uptime: "10s",
      restart_delay: 5000,
      max_memory_restart: "64M"
    },
    {
      name: "salathanie-sensors",
      script: "/data/data/com.termux/files/home/live-command-center/nodes/telemetry-spine/android_sensors.py",
      interpreter: "python3",
      max_restarts: 5,
      min_uptime: "10s",
      restart_delay: 5000,
      max_memory_restart: "48M"
    }
  ]
};
