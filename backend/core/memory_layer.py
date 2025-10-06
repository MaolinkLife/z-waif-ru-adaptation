"""Legacy compatibility wrapper for the former MemoryLayer implementation."""

from __future__ import annotations

from typing import Any, Dict

from modules.memory import MemoryModule
from services.logger_service import AuditStatus, log_audit_entry


class MemoryLayer:
    """Thin wrapper that delegates to the new MemoryModule."""

    def __init__(self) -> None:
        self._module = MemoryModule()
        log_audit_entry(
            "memory_layer.deprecated",
            "[MemoryLayer] Legacy wrapper initialised. Use MemoryModule instead.",
            AuditStatus.WARNING,
        )

    async def get_context(self, current_message: Dict[str, Any]) -> Dict[str, Any]:
        result = await self._module.collect_context(
            current_message.get("content", ""), current_message
        )
        return result.context

    async def get_lore_context(self, text: str, *_args, **_kwargs) -> Dict[str, Any]:
        return await self._module.collect_lore_context(text)
