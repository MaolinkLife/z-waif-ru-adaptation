# ===========================================================
# Module: rag_service.py
# Purpose: Compatibility wrappers around the MemoryModule lore helpers
# ===========================================================

from typing import Any, Dict, List

from services.logger_service import AuditStatus, log_audit_entry
from modules.memory import MemoryModule

_memory_module = MemoryModule()


async def retrieve_lore_fragments(
    text: str,
    top_k: int = 5,
    min_similarity: float = 0.75,
) -> List[Dict[str, Any]]:
    """Async wrapper that delegates lore retrieval to MemoryModule."""
    if not text or not text.strip():
        return []

    context = await _memory_module.collect_lore_context(text)
    entries: List[Dict[str, Any]] = context.get("raw_lore_entries", [])

    log_audit_entry(
        event_type="rag_lore_lookup",
        msg="[RAG] Lore fragments retrieved via MemoryModule",
        status=AuditStatus.INFO,
        details={
            "requested_top_k": top_k,
            "requested_threshold": min_similarity,
            "returned": len(entries),
        },
    )

    return entries


def format_lore_block(lore_entries: List[Dict[str, Any]]) -> str:
    """Formatting helper preserved for backward compatibility."""
    if not lore_entries:
        return ""

    bullet_lines: List[str] = []
    for entry in lore_entries:
        title = entry.get("title") or ""
        content = entry.get("content") or ""
        bullet_lines.append(f"• {title}: {content}" if title else f"• {content}")

    block = "\n".join(bullet_lines)

    log_audit_entry(
        event_type="rag_format",
        msg="Lore block prepared",
        status=AuditStatus.INFO,
        details={"entries_count": len(lore_entries)},
    )

    return f"[CONTEXT]\n{block}\n"
