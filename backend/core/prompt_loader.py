"""Utility for loading character system prompts."""

from __future__ import annotations

import os
import yaml

from services.config_service import get_config_value
from services.logger_service import log_audit_entry, AuditStatus
from utils.open_file_w_utf8 import open_utf8


def load_system_prompt() -> str:
    base_path = os.path.join(os.path.dirname(__file__), "..", "config", "characters")
    char_name = get_config_value("char_name", default="default")
    filename = f"{char_name}.yaml"
    full_path = os.path.join(base_path, filename)
    fallback_path = os.path.join(base_path, "default.yaml")

    try:
        if os.path.exists(full_path):
            with open_utf8(full_path, "r") as file:
                data = yaml.safe_load(file)
                return data.get("prompt", "")
        if os.path.exists(fallback_path):
            with open_utf8(fallback_path, "r") as file:
                data = yaml.safe_load(file)
                return data.get("prompt", "")
        log_audit_entry(
            event_type="character_prompt_not_found",
            msg="[PromptLoader]: Character prompt not found",
            status=AuditStatus.ERROR,
        )
        return "[System Error] Character prompt not found."
    except Exception as exc:  # pragma: no cover
        log_audit_entry(
            event_type="prompt_loading_failed",
            msg="[PromptLoader]: Prompt loading failed",
            status=AuditStatus.ERROR,
            details={"error": str(exc)},
        )
        return "[System Error] Prompt loading failed."
