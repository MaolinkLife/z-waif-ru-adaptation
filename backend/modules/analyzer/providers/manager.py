"""Provider manager for analyzer module."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Tuple

from services.config_service import get_config_value
from services.logger_service import AuditStatus, log_audit_entry
from services.localization_service import get_text

from .base import AnalyzerProvider
from .openrouter import OpenRouterAnalyzerProvider
from .ollama import OllamaAnalyzerProvider


class AnalyzerProviderManager:
    """Manages the chain of analyzer providers with fallbacks."""

    def __init__(self) -> None:
        self._registry: Dict[str, AnalyzerProvider] = {
            "openrouter": OpenRouterAnalyzerProvider(),
            "ollama": OllamaAnalyzerProvider(),
        }

    async def analyze(
        self, content: str, context: Dict[str, Any]
    ) -> Tuple[Optional[Dict[str, Any]], Optional[str], List[str]]:
        errors: List[str] = []
        for provider in self._resolve_providers():
            if not provider.is_available():
                log_audit_entry(
                    "analyzer_provider_unavailable",
                    get_text(
                        "analyzer.provider_unavailable",
                        params={"provider": provider.name},
                        default=f"[Analyzer] Provider '{provider.name}' unavailable.",
                    ),
                    AuditStatus.INFO,
                    message_key="analyzer.provider_unavailable",
                    message_args={"provider": provider.name},
                )
                errors.append(f"{provider.name}_unavailable")
                continue

            result = await provider.analyze(content, context)
            if result:
                return result, provider.name, errors

            errors.append(f"{provider.name}_failed")

        return None, None, errors

    def register(self, provider: AnalyzerProvider) -> None:
        self._registry[provider.name] = provider

    def set_providers(self, providers: Iterable[AnalyzerProvider]) -> None:
        self._registry = {provider.name: provider for provider in providers}

    def _resolve_providers(self) -> List[AnalyzerProvider]:
        active = get_config_value("analyzer.active_provider", "openrouter")
        fallback = get_config_value("analyzer.fallback_order", [])

        order: List[str] = []
        if isinstance(active, str) and active:
            order.append(active)

        if isinstance(fallback, list):
            for name in fallback:
                if isinstance(name, str):
                    order.append(name)

        resolved: List[AnalyzerProvider] = []
        for name in order:
            provider = self._registry.get(name)
            if provider and provider not in resolved:
                resolved.append(provider)

        for provider in self._registry.values():
            if provider not in resolved:
                resolved.append(provider)

        return resolved
