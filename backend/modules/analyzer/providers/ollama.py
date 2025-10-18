"""Ollama-based analyzer provider."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

from constants.prompts import COGNITIVE_ANALYSIS_PROMPT
from constants.settings import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE
from modules.ollama import client as ollama_client
from services.config_service import get_config_value
from services.logger_service import AuditStatus, log_audit_entry

from .base import AnalyzerProvider


class OllamaAnalyzerProvider(AnalyzerProvider):
    name = "ollama"

    def _get_settings(self) -> Dict[str, Any]:
        cfg = get_config_value("analyzer.providers.ollama", {}) or {}
        return {
            "model": cfg.get("model") or get_config_value("api.model", "llama3.2"),
            "temperature": float(cfg.get("temperature", DEFAULT_TEMPERATURE)),
            "max_tokens": int(cfg.get("max_tokens", DEFAULT_MAX_TOKENS)),
        }

    def is_available(self) -> bool:
        return True

    async def analyze(
        self, content: str, context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        settings = self._get_settings()

        try:
            log_audit_entry(
                "analyzer_ollama_start",
                "[Analyzer] Starting analysis.",
                AuditStatus.INFO,
                details={"model": settings["model"]},
            )
            result = await asyncio.to_thread(
                self._call_ollama,
                content,
                context,
                settings,
            )
            log_audit_entry(
                "analyzer_ollama_success",
                "[Analyzer] Analysis completed successfully.",
                AuditStatus.SUCCESS,
            )
            return result
        except Exception as exc:  # pragma: no cover
            log_audit_entry(
                "analyzer_ollama_error",
                "[Analyzer] Error during analysis.",
                AuditStatus.ERROR,
                details={"error": str(exc), "error_type": type(exc).__name__},
            )
            return None

    @staticmethod
    def _call_ollama(
        content: str,
        context: Dict[str, Any],
        settings: Dict[str, Any],
    ) -> Dict[str, Any]:
        user_prompt_content = f'User message: "{content}"'
        if context:
            user_prompt_content += (
                f"\n\nContext:\n{json.dumps(context, ensure_ascii=False, indent=2)}"
            )
        history = [
            {"role": "system", "content": COGNITIVE_ANALYSIS_PROMPT},
            {"role": "user", "content": user_prompt_content},
        ]
        options = {
            "temperature": settings["temperature"],
            "max_tokens": settings["max_tokens"],
        }
        response = ollama_client.chat(
            history,
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
