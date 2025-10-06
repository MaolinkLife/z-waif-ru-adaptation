from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, Optional


@dataclass
class GenerateRequest:
    """Универсальный запрос на генерацию текста."""

    messages: Iterable[Dict[str, Any]]
    options: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerateResult:
    """Результат генерации в универсальном формате."""

    provider: str
    content: str
    raw: Any = None
    reasoning: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GenerateStreamChunk:
    """Универсальный кусок потоковой генерации."""

    provider: str
    content: str
    raw: Any = None
    done: bool = False
    reasoning: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
