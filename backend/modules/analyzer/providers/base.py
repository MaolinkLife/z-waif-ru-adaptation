"""Base interfaces for analyzer providers."""

from __future__ import annotations

from typing import Any, Dict, Optional


class AnalyzerProvider:
    """Interface for analyzer providers."""

    name: str = "unknown"

    async def analyze(
        self, content: str, context: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def is_available(self) -> bool:
        return True
