"""OpenRouter-backed MoralMatrix provider."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Optional

from openai import OpenAI

from constants.prompts import MORAL_MATRIX_PROVIDER_PROMPT
from constants.settings import (
    DEFAULT_HOST,
    DEFAULT_MAX_TOKENS,
    DEFAULT_MODEL,
    DEFAULT_TEMPERATURE,
    OPENROUTER_BASE_URL,
    PROJECT_NAME,
)
from services.config_service import get_config_value
from services.logger_service import AuditStatus, log_audit_entry

from .base import MoralMatrixProvider


class OpenRouterMoralProvider(MoralMatrixProvider):
    name = "openrouter"

    def _get_settings(self) -> Dict[str, Any]:
        cfg = get_config_value("moral.providers.openrouter", {}) or {}
        return {
            "api_key": cfg.get("api_key", ""),
            "model": cfg.get("model") or DEFAULT_MODEL,
            "temperature": float(cfg.get("temperature", DEFAULT_TEMPERATURE)),
            "max_tokens": int(cfg.get("max_tokens", min(DEFAULT_MAX_TOKENS, 512))),
        }

    def is_available(self) -> bool:
        return bool(self._get_settings()["api_key"])

    async def run(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        settings = self._get_settings()
        api_key = settings["api_key"]

        if not api_key:
            log_audit_entry(
                "moral_matrix_provider_openrouter_skipped",
                "[MoralMatrix/OpenRouter] API key missing. Skipping.",
                AuditStatus.WARNING,
            )
            return None

        try:
            log_audit_entry(
                "moral_matrix_provider_openrouter_start",
                "[MoralMatrix/OpenRouter] Provider start.",
                AuditStatus.INFO,
                details={"model": settings["model"]},
            )
            result = await asyncio.to_thread(
                self._call_openrouter,
                payload,
                settings,
            )
            log_audit_entry(
                "moral_matrix_provider_openrouter_success",
                "[MoralMatrix/OpenRouter] Provider completed.",
                AuditStatus.SUCCESS,
            )
            return result
        except Exception as exc:  # pragma: no cover
            log_audit_entry(
                "moral_matrix_provider_openrouter_error",
                "[MoralMatrix/OpenRouter] Provider error.",
                AuditStatus.ERROR,
                details={"error": str(exc), "error_type": type(exc).__name__},
            )
            return None

    def _call_openrouter(
        self, payload: Dict[str, Any], settings: Dict[str, Any]
    ) -> Dict[str, Any]:
        client = OpenAI(base_url=OPENROUTER_BASE_URL, api_key=settings["api_key"])

        completion = client.chat.completions.create(
            extra_headers={
                "HTTP-Referer": DEFAULT_HOST,
                "X-Title": PROJECT_NAME,
            },
            model=settings["model"],
            messages=[
                {"role": "system", "content": MORAL_MATRIX_PROVIDER_PROMPT},
                {
                    "role": "user",
                    "content": json.dumps(payload, ensure_ascii=False, indent=2),
                },
            ],
            temperature=settings["temperature"],
            max_tokens=settings["max_tokens"],
            response_format={"type": "json_object"},
        )

        response_content = completion.choices[0].message.content
        if not response_content or not response_content.strip():
            raise ValueError("OpenRouter returned empty response.")
        return json.loads(response_content)

