"""Базовые классы и исключения для генеративных провайдеров."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import AsyncIterator

from modules.generative.types import GenerateRequest, GenerateResult, GenerateStreamChunk


class ProviderError(Exception):
    """Ошибка конкретного провайдера генерации."""


class ProviderNotAvailable(ProviderError):
    """Провайдер недоступен (не настроен, отсутствует ключ и т.п.)."""


class StreamingNotSupported(ProviderError):
    """Потоковая генерация не поддерживается провайдером."""


class GenerateProvider(ABC):
    """Базовый интерфейс для провайдеров генерации."""

    name: str

    def is_available(self) -> bool:
        return True

    def supports_streaming(self) -> bool:
        return False

    @abstractmethod
    def generate(self, request: GenerateRequest) -> GenerateResult:
        """Запустить синхронную генерацию."""

    async def stream(self, request: GenerateRequest) -> AsyncIterator[GenerateStreamChunk]:
        """Потоковая генерация. По умолчанию не поддерживается."""
        raise StreamingNotSupported(f"Provider {self.name} не поддерживает streaming")
