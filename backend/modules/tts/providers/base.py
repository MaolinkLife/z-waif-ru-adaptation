"""Base classes and exceptions for TTS providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from modules.tts.types import TTSRequest, TTSResult


class TTSProviderError(Exception):
    """Общее исключение провайдеров синтеза речи."""


class TTSProvider(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def synthesize(self, request: TTSRequest, output_path: str) -> TTSResult:
        pass

    def shutdown(self) -> None:
        """Освобождение ресурсов."""
        return None
