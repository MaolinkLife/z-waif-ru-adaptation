"""Analyzer module orchestrating cognitive analysis providers."""

from __future__ import annotations

from typing import Any, Dict

from services.logger_service import AuditStatus, log_audit_entry

from .providers.manager import AnalyzerProviderManager

AnalyzerOutput = Dict[str, Any]


class AnalyzerModule:
    """High-level orchestrator for cognitive analysis."""

    def __init__(self) -> None:
        self.provider_manager = AnalyzerProviderManager()
        self._default_provider_name = "default"

    async def analyze(self, input_raw: Dict[str, Any]) -> AnalyzerOutput:
        content = (input_raw.get("content") or "").strip()
        message_meta = self._build_message_meta(input_raw)

        if not content:
            log_audit_entry(
                "analyzer_empty_content",
                "[Analyzer] Пустой ввод. Возвращаю дефолтный анализ.",
                AuditStatus.WARNING,
                details={"message_meta": message_meta},
            )
            return self._wrap_default(content, reason="empty_input", meta=message_meta)

        result, provider_name, errors = await self.provider_manager.analyze(
            content, message_meta
        )

        if result:
            return {
                "metadata": result,
                "provider": provider_name or self._default_provider_name,
                "errors": errors,
                "message_meta": message_meta,
            }

        errors.append("all_providers_failed")
        metadata = self._build_default_metadata(content)
        return {
            "metadata": metadata,
            "provider": self._default_provider_name,
            "errors": errors,
            "message_meta": message_meta,
        }

    @staticmethod
    def _build_message_meta(input_raw: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "message_id": input_raw.get("id"),
            "timestamp": input_raw.get("timestamp"),
            "message_type": input_raw.get("message_type", "user_message"),
            "source": input_raw.get("source"),
            "media_count": len(input_raw.get("media") or []),
        }

    @staticmethod
    def _build_default_metadata(content: str) -> Dict[str, Any]:
        return {
            "input_analysis": {
                "original_message": content,
                "content_category": "casual_conversation",
                "dominant_themes": ["general"],
                "emotional_tone": {
                    "primary": "neutral",
                    "secondary": [],
                    "intensity": 0.5,
                },
                "intent_analysis": {
                    "primary_intent": "general_communication",
                    "context_dependency": "medium",
                },
            },
            "risk_assessment": {
                "content_flags": [],
                "risk_level": 0.0,
                "violated_policies": [],
            },
            "response_guidance": {
                "routing_recommendation": "standard_processing",
                "generation_parameters": {
                    "temperature": 0.7,
                    "sarcasm_level": 0.0,
                    "persona_constraints": ["friendly", "helpful"],
                },
            },
            "memory_tagging": {
                "context_tags": ["general_conversation"],
                "relationship_impact": "neutral",
            },
        }

    def _wrap_default(
        self, content: str, *, reason: str, meta: Dict[str, Any]
    ) -> AnalyzerOutput:
        metadata = self._build_default_metadata(content)
        return {
            "metadata": metadata,
            "provider": self._default_provider_name,
            "errors": [reason],
            "message_meta": meta,
        }
