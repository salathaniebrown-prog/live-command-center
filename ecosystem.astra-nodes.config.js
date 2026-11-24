module.exports = {
  apps: [
    {
      name: "astra-webhook-8115",
      script: "webhook_node.py",
      interpreter: "python3",
      max_memory_restart: "150M",
      env: {
        ASTRA_WEBHOOK_SECRET: process.env.ASTRA_WEBHOOK_SECRET || "astra_dev_secret_2026"
      }
    },
    {
      name: "astra-model-router",
      script: "model_router.py",
      interpreter: "python3",
      max_memory_restart: "200M",
      env: {
        GEMINI_API_KEY: process.env.GEMINI_API_KEY || ""
      }
    }
  ]
};
