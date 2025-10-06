from __future__ import annotations

from typing import AsyncIterator, Dict, Iterable, List

from modules.generative.providers.base import GenerateProvider, ProviderError
from modules.generative.providers.ollama import OllamaGenerateProvider
from modules.generative.providers.openrouter import OpenRouterGenerateProvider
from modules.generative.types import GenerateRequest, GenerateResult, GenerateStreamChunk
from services.config_service import get_config_value
from services.logger_service import AuditStatus, log_audit_entry


class NoProviderResolved(ProviderError):
    """Не удалось подобрать рабочий провайдер."""


class GenerationManager:
    def __init__(self) -> None:
        self._providers: Dict[str, GenerateProvider] = {
            "ollama": OllamaGenerateProvider(),
            "openrouter": OpenRouterGenerateProvider(),
        }

    def _ordered_provider_names(self) -> List[str]:
        active = get_config_value("api.active_provider", "ollama")
        fallbacks = get_config_value("api.fallback_order", []) or []
        ordered = [active] if active else []
        for name in fallbacks:
            if name not in ordered:
                ordered.append(name)
        return ordered or list(self._providers.keys())

    def _iter_providers(self) -> Iterable[GenerateProvider]:
        for name in self._ordered_provider_names():
            provider = self._providers.get(name)
            if provider:
                yield provider

    def generate(self, request: GenerateRequest) -> GenerateResult:
        errors: List[dict] = []

        for provider in self._iter_providers():
            if not provider.is_available():
                errors.append({"provider": provider.name, "reason": "not_available"})
                continue
            try:
                result = provider.generate(request)
                log_audit_entry(
                    event_type="generator_provider_resolved",
                    msg="[Generator] Провайдер выбран",
                    status=AuditStatus.INFO,
                    details={"provider": provider.name},
                )
                return result
            except ProviderError as exc:
                errors.append({"provider": provider.name, "reason": str(exc)})
                log_audit_entry(
                    event_type="generator_provider_error",
                    msg="[Generator] Ошибка провайдера",
                    status=AuditStatus.ERROR,
                    details={"provider": provider.name, "error": str(exc)},
                )

        raise NoProviderResolved(str(errors))

    async def stream(self, request: GenerateRequest) -> AsyncIterator[GenerateStreamChunk]:
        errors: List[dict] = []

        for provider in self._iter_providers():
            if not provider.is_available():
                errors.append({"provider": provider.name, "reason": "not_available"})
                continue
            if not provider.supports_streaming():
                errors.append({"provider": provider.name, "reason": "not_streaming"})
                continue
            try:
                async for chunk in provider.stream(request):
                    yield chunk
                log_audit_entry(
                    event_type="generator_provider_stream_resolved",
                    msg="[Generator] Потоковый провайдер выбран",
                    status=AuditStatus.INFO,
                    details={"provider": provider.name},
                )
                return
            except ProviderError as exc:
                errors.append({"provider": provider.name, "reason": str(exc)})
                log_audit_entry(
                    event_type="generator_provider_stream_error",
                    msg="[Generator] Ошибка потокового провайдера",
                    status=AuditStatus.ERROR,
                    details={"provider": provider.name, "error": str(exc)},
                )
                continue

        raise NoProviderResolved(str(errors))


generation_manager = GenerationManager()

__all__ = [
    "GenerationManager",
    "generation_manager",
    "NoProviderResolved",
]
