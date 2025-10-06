# ===========================================================
# Module: context_builder.py
# Purpose: Extracts context fragments from history
# Depends on: database_service
# =========================================================

from services.database_service import get_full_history
from services.logger_service import log_audit_entry, AuditStatus
import re

# Extract keywords (4+ characters, no stop words yet)
def extract_keywords(text: str) -> list:
    words = re.findall(r"\b\w{4,}\b", text.lower())
    return list(set(words))


# Forms a block with "memories" from history
def build_memory_context(user_input: str, character: str, max_hits: int = 3) -> str:
    keywords = extract_keywords(user_input)
    if not keywords:
        log_audit_entry(
            event_type="memory_keywords",
            msg="❌ No keywords extracted for memory",
            status=AuditStatus.WARNING,
            details={"input": user_input}
        )
        return ""

    history = get_full_history(character)
    relevant = []

    # We go through the story from the last to the first
    for entry in reversed(history):
        message_text = entry.get("content", "").lower()
        if any(word in message_text for word in keywords):
            relevant.append(entry)
            if len(relevant) >= max_hits:
                break

    if not relevant:
        log_audit_entry(
            event_type="memory_context",
            msg="Nothing similar was found in memory",
            status=AuditStatus.INFO,
            details={"keywords": keywords}
        )
        return ""

    log_audit_entry(
        event_type="memory_context",
        msg=f"Found {len(relevant)} matches from history",
        status=AuditStatus.INFO,
        details={"keywords": keywords, "entries": [r["content"] for r in relevant]}
    )

    memory_block = "[MEMORY CONTEXT]\n"
    for r in relevant:
        timestamp = r.get("timestamp", "unknown")
        role = r.get("role", "unknown").capitalize()
        content = r.get("content", "")
        memory_block += f"{timestamp} — {role}: {content}\n"

    return memory_block + "\n"
