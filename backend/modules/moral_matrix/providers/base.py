"""Base provider interfaces for MoralMatrix narrative/directive generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional


class MoralMatrixProvider(ABC):
    """Base provider used to refine MoralMatrix evaluation via LLM or heuristics."""

    name: str = "base"

    def is_available(self) -> bool:
        return True

    @abstractmethod
    async def run(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Evaluate payload and return directive metadata."""

