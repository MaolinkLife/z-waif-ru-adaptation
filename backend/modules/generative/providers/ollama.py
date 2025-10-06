from __future__ import annotations

from typing import Any, AsyncIterator, Dict, Iterable, List

from modules.generative.providers.base import GenerateProvider, ProviderError
from modules.generative.types import GenerateRequest, GenerateResult, GenerateStreamChunk
from modules.ollama import client as ollama_client
from services.config_service import get_config_value
from services.logger_service import AuditStatus, log_audit_entry


class OllamaGenerateProvider(GenerateProvider):
    name = "ollama"

    def supports_streaming(self) -> bool:
        return True

    def _get_provider_config(self) -> Dict[str, Any]:
        provider_cfg = get_config_value("api.providers.ollama", {}) or {}
        # Backward compatibility: падаем в api.model, если в providers нет model.
        legacy_model = get_config_value("api.model")
        if legacy_model and "model" not in provider_cfg:
            provider_cfg["model"] = legacy_model
        return provider_cfg

    @staticmethod
    def _ensure_list(messages: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if isinstance(messages, list):
            return messages
        return list(messages)

    def generate(self, request: GenerateRequest) -> GenerateResult:
        cfg = self._get_provider_config()
        model = cfg.get("model")
        if not model:
            raise ProviderError("Ollama provider: не задана модель")

        messages = self._ensure_list(request.messages)

        log_audit_entry(
            event_type="generator_ollama_start",
            msg="[Generator/Ollama] Запуск синхронной генерации",
            status=AuditStatus.INFO,
            details={"model": model},
        )

        raw = ollama_client.chat(messages, request.options, model=model)
        content = raw.get("message", {}).get("content", "")

        log_audit_entry(
            event_type="generator_ollama_success",
            msg="[Generator/Ollama] Генерация завершена",
            status=AuditStatus.SUCCESS,
            details={"model": model},
        )

        return GenerateResult(
            provider=self.name,
            content=content,
            raw=raw,
            metadata={"model": model},
        )

    async def stream(self, request: GenerateRequest) -> AsyncIterator[GenerateStreamChunk]:
        cfg = self._get_provider_config()
        model = cfg.get("model")
        if not model:
            raise ProviderError("Ollama provider: не задана модель")

        messages = self._ensure_list(request.messages)

        log_audit_entry(
            event_type="generator_ollama_stream_start",
            msg="[Generator/Ollama] Запуск потоковой генерации",
            status=AuditStatus.INFO,
            details={"model": model},
        )

        async for chunk in ollama_client.stream_chat(messages, request.options, model=model):
            if not chunk:
                continue
            if "error" in chunk:
                raise ProviderError(chunk["error"])
            content = chunk.get("message", {}).get("content", "")
            yield GenerateStreamChunk(
                provider=self.name,
                content=content,
                raw=chunk,
                done=bool(chunk.get("done")),
                metadata={"model": model},
            )

        log_audit_entry(
            event_type="generator_ollama_stream_success",
            msg="[Generator/Ollama] Потоковая генерация завершена",
            status=AuditStatus.SUCCESS,
            details={"model": model},
        )
