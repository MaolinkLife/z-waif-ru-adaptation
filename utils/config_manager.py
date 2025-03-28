import json
import os

CONFIG_PATH = "config.json"
DEFAULT_CONFIG = {
    "char_name": "default_waifu",
    "voice": {
        "output_id": 0,
        "windows_output_id": 13,
        "language": "ru-RU",
        "voice_language": "ru-RU-SvetlanaNeural",
        "use_rvc": False
    },
    "modules": {
        "vtube_studio": True,
        "whisper": True
    }
}


def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}  # return empty config
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as file:
        json.dump(config, file, indent=4, ensure_ascii=False)


def get_config_value(path: str, default=None):
    keys = path.split(".")
    config = load_config()
    for key in keys:
        config = config.get(key, {})
    return config or default


def set_config_value(path: str, value):
    keys = path.split(".")
    config = load_config()
    ref = config
    for key in keys[:-1]:
        ref = ref.setdefault(key, {})
    ref[keys[-1]] = value
    save_config(config)


def ensure_config_exists():
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)