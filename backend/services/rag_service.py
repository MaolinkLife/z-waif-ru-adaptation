# ===========================================================
# Module: rag_service.py
# Purpose: Retrieve relevant lore from the DB for response generation
# ===========================================================

from services.logger_service import log_audit_entry, AuditStatus
from modules.memory import lorebook


def retrieve_lore_fragments(
    text: str,
    top_k: int = 5,
    min_similarity: float = 0.75,
):
    if not text.strip():
        return []

    try:
        entries = lorebook.search_entries(
            query=text,
            top_k=top_k,
            min_similarity=min_similarity,
        )
        return entries
    except Exception as exc:
        log_audit_entry(
            event_type="rag_lore_error",
            msg="[RAG] Failed to retrieve lore fragments",
            status=AuditStatus.ERROR,
            details={"error": str(exc)},
        )
        return []


# Format lore entries for the prompt
def format_lore_block(lore_entries: list) -> str:
    if not lore_entries:
        return ""

    bullet_lines = []
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
