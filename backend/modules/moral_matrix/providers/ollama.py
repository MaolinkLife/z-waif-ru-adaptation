"""Ollama-backed MoralMatrix provider."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

from constants.prompts import MORAL_MATRIX_PROVIDER_PROMPT
from constants.settings import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
from modules.ollama import client as ollama_client
from services.config_service import get_config_value
from services.logger_service import AuditStatus, log_audit_entry

from .base import MoralMatrixProvider


class OllamaMoralProvider(MoralMatrixProvider):
    name = "ollama"

    def _get_settings(self) -> Dict[str, Any]:
        cfg = get_config_value("moral.providers.ollama", {}) or {}
        return {
            "model": cfg.get("model") or get_config_value("api.model", "llama3.2"),
            "temperature": float(cfg.get("temperature", DEFAULT_TEMPERATURE)),
            "max_tokens": int(cfg.get("max_tokens", min(DEFAULT_MAX_TOKENS, 512))),
        }

    async def run(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        settings = self._get_settings()
        try:
            log_audit_entry(
                "moral_matrix_provider_ollama_start",
                "[MoralMatrix] Provider start.",
                AuditStatus.INFO,
                details={"model": settings["model"]},
            )
            result = await asyncio.to_thread(
                self._call_ollama,
                payload,
                settings,
            )
            log_audit_entry(
                "moral_matrix_provider_ollama_success",
                "[MoralMatrix] Provider completed.",
                AuditStatus.SUCCESS,
            )
            return result
        except Exception as exc:  # pragma: no cover
            log_audit_entry(
                "moral_matrix_provider_ollama_error",
                "[MoralMatrix] Provider error.",
                AuditStatus.ERROR,
                details={"error": str(exc), "error_type": type(exc).__name__},
            )
            return None

    @staticmethod
    def _call_ollama(
        payload: Dict[str, Any], settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        conversation = [
            {"role": "system", "content": MORAL_MATRIX_PROVIDER_PROMPT},
            {
                "role": "user",
                "content": json.dumps(payload, ensure_ascii=False, indent=2),
            },
        ]
        options = {
            "temperature": settings["temperature"],
            "max_tokens": settings["max_tokens"],
        }
        response = ollama_client.chat(
            conversation,
            options,
            model=settings["model"],
        )
        assistant_content = (
            response.get("message", {}).get("content", "")
            if isinstance(response, dict)
            else ""
        )
        if not assistant_content.strip():
            raise ValueError("Ollama returned empty response.")
        return json.loads(assistant_content)
