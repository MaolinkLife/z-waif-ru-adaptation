from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator, Dict, Iterable, List

from openai import OpenAI

from constants.settings import (
    DEFAULT_MAX_TOKENS,
    DEFAULT_TEMPERATURE,
    OPENROUTER_BASE_URL,
)
from modules.generative.providers.base import GenerateProvider, ProviderError
from modules.generative.types import (
    GenerateRequest,
    GenerateResult,
    GenerateStreamChunk,
)
from services.config_service import get_config_value
from services.logger_service import AuditStatus, log_audit_entry


class OpenRouterGenerateProvider(GenerateProvider):
    name = "openrouter"

    def is_available(self) -> bool:
        return bool(self._get_provider_config().get("api_key"))

    def supports_streaming(self) -> bool:
        return True

    def _get_provider_config(self) -> Dict[str, Any]:
        cfg = get_config_value("api.providers.openrouter", {}) or {}
        return {
            "api_key": cfg.get("api_key", ""),
            "model": cfg.get("model", "openai/gpt-4o-mini"),
            "temperature": cfg.get("temperature", DEFAULT_TEMPERATURE),
            "max_tokens": cfg.get("max_tokens", DEFAULT_MAX_TOKENS),
            "base_url": cfg.get("base_url", OPENROUTER_BASE_URL),
        }

    @staticmethod
    def _ensure_list(messages: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if isinstance(messages, list):
            return messages
        return list(messages)

    def _compose_settings(
        self, request: GenerateRequest, cfg: Dict[str, Any]
    ) -> Dict[str, Any]:
        options = request.options or {}
        return {
            "temperature": float(options.get("temperature", cfg["temperature"])),
            "max_tokens": int(options.get("max_tokens", cfg["max_tokens"])),
            "top_p": options.get("top_p"),
        }

    def _build_client(self, cfg: Dict[str, Any]) -> OpenAI:
        if not cfg.get("api_key"):
            raise ProviderError("OpenRouter provider: отсутствует API ключ")
        return OpenAI(base_url=cfg["base_url"], api_key=cfg["api_key"])

    def generate(self, request: GenerateRequest) -> GenerateResult:
        cfg = self._get_provider_config()
        client = self._build_client(cfg)
        messages = self._ensure_list(request.messages)
        settings = self._compose_settings(request, cfg)

        print("[Generator] OpenRouter: синхронная генерация.")
        log_audit_entry(
            event_type="generator_openrouter_start",
            msg="[Generator/OpenRouter] Запуск синхронной генерации",
            status=AuditStatus.INFO,
            details={
                "model": cfg["model"],
                "messages": messages,
                "options": request.options,
                "metadata": request.metadata,
                "settings": settings,
            },
        )

        try:
            completion = client.chat.completions.create(
                model=cfg["model"],
                messages=messages,
                temperature=settings["temperature"],
                max_tokens=settings["max_tokens"],
                top_p=settings["top_p"],
            )
        except Exception as exc:  # pragma: no cover - внешняя библиотека
            raise ProviderError(str(exc)) from exc

        choice = completion.choices[0]
        content = (choice.message.content or "").strip()

        log_audit_entry(
            event_type="generator_openrouter_success",
            msg="[Generator/OpenRouter] Генерация завершена",
            status=AuditStatus.SUCCESS,
            details={
                "model": cfg["model"],
                "response": completion.model_dump(),
                "content_length": len(content),
            },
        )
        print("[Generator] OpenRouter: ответ получен.")

        return GenerateResult(
            provider=self.name,
            content=content,
            raw=completion.model_dump(),
            metadata={"model": cfg["model"]},
        )

    async def stream(
        self, request: GenerateRequest
    ) -> AsyncIterator[GenerateStreamChunk]:
        cfg = self._get_provider_config()
        client = self._build_client(cfg)
        messages = self._ensure_list(request.messages)
        settings = self._compose_settings(request, cfg)

        print("[Generator] OpenRouter: потоковая генерация.")
        log_audit_entry(
            event_type="generator_openrouter_stream_start",
            msg="[Generator/OpenRouter] Запуск потоковой генерации",
            status=AuditStatus.INFO,
            details={
                "model": cfg["model"],
                "messages": messages,
                "options": request.options,
                "metadata": request.metadata,
                "settings": settings,
            },
        )

        try:
            stream = client.chat.completions.create(
                model=cfg["model"],
                messages=messages,
                temperature=settings["temperature"],
                max_tokens=settings["max_tokens"],
                top_p=settings["top_p"],
                stream=True,
            )
        except Exception as exc:  # pragma: no cover
            raise ProviderError(str(exc)) from exc

        loop = asyncio.get_running_loop()

        async def iterate() -> AsyncIterator[GenerateStreamChunk]:
            try:
                while True:
                    chunk = await loop.run_in_executor(None, self._next_chunk, stream)
                    if chunk is None:
                        break
                    yield chunk
            finally:
                stream.close()

        index = 0
        async for chunk in iterate():
            index += 1
            raw_payload = (
                chunk.raw
                if isinstance(chunk.raw, (dict, list, str, int, float, bool, type(None)))
                else str(chunk.raw)
            )
            # log_audit_entry(
            #     event_type="generator_openrouter_stream_chunk",
            #     msg="[Generator/OpenRouter] Получен потоковый chunk.",
            #     status=AuditStatus.INFO,
            #     details={
            #         "model": cfg["model"],
            #         "index": index,
            #         "content": chunk.content,
            #         "done": chunk.done,
            #         "raw": raw_payload,
            #     },
            # )
            yield chunk

        log_audit_entry(
            event_type="generator_openrouter_stream_success",
            msg="[Generator/OpenRouter] Потоковая генерация завершена",
            status=AuditStatus.SUCCESS,
            details={"model": cfg["model"], "chunks": index},
        )
        print("[Generator] OpenRouter: поток завершён.")

    def _next_chunk(self, stream) -> GenerateStreamChunk | None:
        try:
            event = next(stream)
        except StopIteration:
            return None

        if not event or not getattr(event, "choices", None):
            return GenerateStreamChunk(
                provider=self.name, content="", raw=None, done=False
            )

        choice = event.choices[0]
        delta = getattr(choice, "delta", None)
        content = ""
        if delta and getattr(delta, "content", None):
            content = delta.content

        done = bool(choice.finish_reason)

        return GenerateStreamChunk(
            provider=self.name,
            content=content or "",
            raw=event.model_dump() if hasattr(event, "model_dump") else event,
            done=done,
        )
