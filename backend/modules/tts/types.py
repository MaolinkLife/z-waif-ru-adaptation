from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class TTSRequest:
    text: str
    language: str = "auto"
    voice: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TTSResult:
    success: bool
    provider: Optional[str] = None
    file_path: Optional[str] = None
    duration_ms: Optional[int] = None
    error: Optional[str] = None
    fallback_used: bool = False
    attempted_engines: Optional[list[str]] = None
