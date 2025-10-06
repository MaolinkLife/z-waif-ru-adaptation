import json
import os

# Correct path to config/port-config.json
config_path = os.path.join("config", "port-config.json")

with open(config_path, encoding="utf-8") as f:
    ports = json.load(f)

print(f'set FRONTEND_PORT={ports.get("frontend", 4200)}')
print(f'set BACKEND_PORT={ports.get("backend", 8000)}')