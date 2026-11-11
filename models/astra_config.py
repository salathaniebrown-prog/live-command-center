import os

CONFIG = {
    "TELEMETRY_HOST": "127.0.0.1",
    "TELEMETRY_PORT": 8081,
    "API_TOKEN": os.getenv("ASTRA_API_TOKEN", "default_dev_token_secure")
}
