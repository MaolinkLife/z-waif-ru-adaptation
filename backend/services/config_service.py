# ===========================================================
# Module: config_service.py
# Purpose: Managing LIM configuration. Loading, saving,
# updating and caching values ​​from config.json.
# Used in: services, utilities, core — anywhere configuration is needed
# Features:
# - Uses caching (_config_cache) to minimize I/O
# - Allows fine-grained modification of values ​​via get/set
# - Supports bulk update with validation (_recursive_update)
# ==========================================================
from typing import Dict, Any, Optional
import json
import os
from utils.open_file_w_utf8 import open_utf8
from services.logger_service import log_audit_entry, AuditStatus
from models.config_model import CONFIG_PATHS
from constants.default_config import DEFAULT_CONFIG

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", CONFIG_PATHS["config"])
PRESETS_PATH = os.path.join(os.path.dirname(__file__), "..", CONFIG_PATHS["presets"])

_config_cache: Optional[dict] = None
_config_mtime: Optional[float] = None


# Creates a config.json file with defaults if it does not exist.
def ensure_config_exists():
    if not os.path.exists(CONFIG_PATH):
        save_config(DEFAULT_CONFIG)
        log_audit_entry(
            event_type="config_created",
            msg="[Config Service]: Create Default Config",
            status=AuditStatus.SUCCESS,
            details={"status": "OK", "path": CONFIG_PATH},
            meta={
                "config_path": CONFIG_PATH,
                "defaultConfig": DEFAULT_CONFIG,
            },
        )


def _load_config_from_file() -> dict:
    global _config_cache, _config_mtime
    ensure_config_exists()
    with open_utf8(CONFIG_PATH, "r") as f:
        _config_cache = json.load(f)
    try:
        _config_mtime = os.path.getmtime(CONFIG_PATH)
    except OSError:
        _config_mtime = None
    return _config_cache


def _save_config_to_file(data: dict):
    with open_utf8(CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)


# Returns the current config (with caching).
def get_config() -> dict:
    global _config_cache, _config_mtime
    if _config_cache is None:
        return _load_config_from_file()

    try:
        current_mtime = os.path.getmtime(CONFIG_PATH)
    except OSError:
        current_mtime = None

    if _config_mtime is None or current_mtime != _config_mtime:
        return _load_config_from_file()

    return _config_cache.copy()


# Overwrites the entire config with new contents.
def save_config(new_data: dict):
    global _config_cache, _config_mtime

    # Validation
    is_valid, errors = validate_config(new_data)
    if not is_valid:
        log_audit_entry(
            event_type="config_validation_error",
            msg="[Config Service]: Config validation failed",
            status=AuditStatus.ERROR,
            details={"errors": errors, "config": new_data},
        )
        raise ValueError(f"Config validation failed: {errors}")

    _config_cache = new_data
    _save_config_to_file(_config_cache)
    try:
        _config_mtime = os.path.getmtime(CONFIG_PATH)
    except OSError:
        _config_mtime = None
    log_audit_entry(
        event_type="config_saved",
        msg="[Config Service]: Save config file",
        status=AuditStatus.SUCCESS,
        details={"status": "OK", "keys": list(new_data.keys())},
        meta={"new_data": new_data},
    )


# Sets the value to the nested path and saves the config
def get_config_value(path: str, default: Any = None) -> Any:
    """Get nested config value by path like 'api.model'"""
    keys = path.split(".")
    config = get_config()
    ref = config

    for key in keys:
        if isinstance(ref, dict) and key in ref:
            ref = ref[key]
        else:
            return default
    return ref


# Returns the value at the path "key1.key2". If not found, returns default
def set_config_value(path: str, value: Any) -> bool:
    """Set nested config value by path like 'api.model'"""
    try:
        keys = path.split(".")
        config = get_config()
        ref = config

        # Reach the required level, creating intermediate dicts when necessary
        for key in keys[:-1]:
            if key not in ref or not isinstance(ref[key], dict):
                ref[key] = {}
            ref = ref[key]

        # Assign the value
        ref[keys[-1]] = value
        save_config(config)
        return True
    except Exception as e:
        log_audit_entry(
            event_type="config_set_error",
            msg=f"[Config Service]: Error setting config value: {path}",
            status=AuditStatus.ERROR,
            details={"error": str(e), "path": path, "value": value},
        )
        return False


def _recursive_update(
    existing: dict, updates: dict, path: str = ""
) -> tuple[list, list]:
    """
    Recursively update the config, returning lists of success and failure paths.
    """
    updated = []
    failed = []

    log_audit_entry(
        event_type="config_debug_recursive_start",
        msg=f"[Config Service]: Starting recursive update",
        status=AuditStatus.INFO,
        details={
            "path": path,
            "updates_keys": (
                list(updates.keys()) if isinstance(updates, dict) else "not_dict"
            ),
            "existing_type": type(existing).__name__,
        },
    )

    for key, value in updates.items():
        current_path = f"{path}.{key}" if path else key

        log_audit_entry(
            event_type="config_debug_recursive_item",
            msg=f"[Config Service]: Processing item in recursive update",
            status=AuditStatus.INFO,
            details={
                "current_path": current_path,
                "key": key,
                "value_type": type(value).__name__,
                "value": (
                    str(value)[:200] + "..."
                    if isinstance(value, (dict, list)) and len(str(value)) > 200
                    else value
                ),
            },
        )

        # Protect existing user_id from being overwritten
        if current_path == "user_id":
            if existing.get(key) not in [None, ""]:
                failed.append(
                    {
                        "path": current_path,
                        "error": "user_id is already set and cannot be changed.",
                    }
                )
                continue

        if isinstance(value, dict) and isinstance(existing.get(key), dict):
            # Recursively update nested dictionaries
            log_audit_entry(
                event_type="config_debug_recursive_nested",
                msg=f"[Config Service]: Recursively updating nested dict",
                status=AuditStatus.INFO,
                details={
                    "path": current_path,
                    "key": key,
                },
            )
            u, f = _recursive_update(existing[key], value, current_path)
            updated.extend(u)
            failed.extend(f)
        else:
            # Update a simple value
            old_value = existing.get(key)
            existing[key] = value
            updated.append(current_path)

            # Log the change
            log_audit_entry(
                event_type="config_key_updated",
                msg=f"[Config Service]: Config key updated: {current_path}",
                status=AuditStatus.SUCCESS,
                details={
                    "path": current_path,
                    "old_value": str(old_value)[:100] if old_value else old_value,
                    "new_value": str(value)[:100] if value else value,
                },
            )

    log_audit_entry(
        event_type="config_debug_recursive_end",
        msg=f"[Config Service]: Finished recursive update",
        status=AuditStatus.INFO,
        details={
            "path": path,
            "updated_count": len(updated),
            "failed_count": len(failed),
        },
    )

    return updated, failed


def validate_config(config: dict) -> tuple[bool, list]:
    """
    Basic validation of the config.
    Returns (is_valid, list_of_errors).
    """
    errors = []

    # Для user_id делаем отдельную проверку - он может быть None при создании дефолтного конфига
    # Но если он есть, то должен быть не пустым
    user_id = config.get("user_id")
    if user_id is not None and user_id == "":
        errors.append("user_id cannot be empty string")

    # Validate voice section
    if "voice" in config:
        voice = config["voice"]
        if not isinstance(voice, dict):
            errors.append("voice must be an object")
        elif voice.get("enabled") and not voice.get("voice_language"):
            errors.append("voice_language is required when voice is enabled")

    # Validate API settings
    if "api" in config:
        api = config["api"]
        if not isinstance(api, dict):
            errors.append("api must be an object")
        else:
            providers = api.get("providers")
            if providers is None or not isinstance(providers, dict):
                errors.append("api.providers must be an object")
            else:
                for name, provider_cfg in providers.items():
                    if not isinstance(provider_cfg, dict):
                        errors.append(f"api.providers.{name} must be an object")
            active_provider = api.get("active_provider")
            if active_provider and providers and active_provider not in providers:
                errors.append(
                    "api.active_provider must exist inside api.providers"
                )
            if not active_provider:
                errors.append("api.active_provider is required")

    if "memory" in config:
        memory_cfg = config["memory"]
        if not isinstance(memory_cfg, dict):
            errors.append("memory must be an object")
        else:
            recent_limit = memory_cfg.get("recent_limit")
            if recent_limit is not None and (
                not isinstance(recent_limit, int) or recent_limit <= 0
            ):
                errors.append("memory.recent_limit must be a positive integer")
            similarity = memory_cfg.get("similarity_threshold")
            if similarity is not None and not isinstance(similarity, (float, int)):
                errors.append("memory.similarity_threshold must be a number")

    # Validate newly added sections
    if "audio" in config and not isinstance(config["audio"], dict):
        errors.append("audio must be an object")

    if "vision" in config and not isinstance(config["vision"], dict):
        errors.append("vision must be an object")

    if "rag" in config:
        rag = config["rag"]
        if not isinstance(rag, dict):
            errors.append("rag must be an object")
        elif rag.get("enabled") and not rag.get("embeddingModel"):
            errors.append("rag.embeddingModel is required when rag is enabled")

    return len(errors) == 0, errors


def update_config_bulk(updates: dict):
    config = get_config()
    updated, failed = _recursive_update(config, updates)
    save_config(config)

    log_audit_entry(
        event_type="config_updated_bulk",
        msg="[Config Service]: Update config fields",
        status=AuditStatus.SUCCESS,
        details={"updated": updated, "failed": failed},
        meta={
            "source": "config",
            "mode": "bulk",
            "config": config,
            "updated": updated,
            "failed": failed,
        },
    )

    # If char_name is updated, we create a character in the DB
    new_char_name = updates.get("char_name")
    # if new_char_name:
    #     database_service.get_or_create_character(new_char_name)

    return updated, failed


def load_generation_presets() -> list:
    if not os.path.exists(PRESETS_PATH):
        return []
    with open_utf8(PRESETS_PATH, "r") as f:
        return json.load(f)


def apply_preset_by_name(preset_name: str) -> bool:
    presets = load_generation_presets()
    matched = next((p for p in presets if p["name"] == preset_name), None)

    if not matched:
        return False

    config = get_config()
    config["generate_settings"] = matched
    save_config(config)
    return True


def get_user_config(user_id: str) -> dict:
    """
    Retrieve config for a specific user.
    Currently returns the global config but prepares for DB support.
    """
    config = get_config()
    if config.get("user_id") == user_id:
        return config
    # TODO: Load per-user config from the DB in the future
    return config


def save_user_config(user_id: str, config: dict) -> bool:
    """
    Save a user's config.
    Currently saves the global config but prepares for DB support.
    """
    if get_config().get("user_id") == user_id:
        save_config(config)
        return True
    # TODO: Persist per-user config to the DB in the future
    return False
