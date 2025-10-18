# ==========================================================
# Module: database_service.py
# Purpose: Central entry point for working with the database.
# Acts as a facade: routes calls to user_service, message_service,
# history_service, character_service depending on db_type.
# ==========================================================

from datetime import datetime, timezone
import json

from services import user_service, message_service, history_service, character_service
from services.storage_service import serialize_media_entries
from services.logger_service import log_error
from services.config_service import get_config_value
from fastapi import HTTPException

db_type = "sqlite"  # later: postgres, etc.


# =========================
# Initialization
# =========================
def create_database():
    if db_type == "sqlite":
        from services.db_core import create_database

        return create_database()
    raise ValueError(f"Unknown database type: {db_type}")


# =========================
# Users
# =========================
def get_or_create_user(name: str, trust_level: int = 0):
    return user_service.get_or_create_user(name, trust_level)


def get_owner():
    return user_service.get_owner()


# =========================
# Characters
# =========================
def get_or_create_character(name: str):
    return character_service.get_or_create_character(name)


# =========================
# Messages
# =========================
def add_message(
    user_id: str, role: str, content: str, dialog_id: str = None, volatile: bool = False
):
    return message_service.add_message(user_id, role, content, dialog_id, volatile)


def get_messages(user_id: str, limit: int = 20):
    return message_service.get_messages(user_id, limit)


# =========================
# History (legacy support)
# =========================
def add_message_to_history(
    character_name: str,
    role: str,
    content: str,
    timestamp: datetime = None,
    media: list | None = None,
    tags: list | None = None,
):
    if isinstance(timestamp, str):
        try:
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        except Exception as e:
            log_error(f"[⚠️ Error parsing timestamp]: {e}")
            timestamp = datetime.now(timezone.utc)

    char = character_service.get_character(character_name)
    if not char:
        raise ValueError(f"Персонаж '{character_name}' не найден")

    return history_service.add_history(
        char.id, role, content, timestamp, media_items=media, tags=tags
    )


def get_history(character_name: str, limit: int = 20, offset: int = 0):
    char = character_service.get_character(character_name)
    if not char:
        return []

    rows = history_service.get_history(char.id, limit, offset)

    return _serialize_history_rows(rows)


def get_history_since(character_name: str, start_time):
    char = character_service.get_character(character_name)
    if not char:
        return []

    rows = history_service.get_history_since(char.id, start_time)
    return _serialize_history_rows(rows)


def delete_message_chain(message_id: str):
    return history_service.delete_message_chain(message_id)


def delete_message(message_id: str):
    return history_service.delete_message(message_id)


async def reroll_message(message_id: str):
    return await history_service.reroll_assistant_message(message_id)


def get_last_user_message_time(character_name: str):
    return history_service.get_last_user_message_time(character_name)


def get_history_by_ids(message_ids):
    return history_service.get_messages_by_ids(message_ids)


def get_last_messages(character_name: str, limit: int = 10):
    return history_service.get_last_messages(character_name, limit)


def get_message_by_id(message_id: str):
    return history_service.get_message_by_id(message_id)


def get_full_history(character_name: str):
    return history_service.get_full_history(character_name)


def get_lorebook_entries():
    character_name = get_config_value("system.char_name")
    return history_service.get_lorebook_entries(character_name)


def add_reasoning_entry(message_id: str, content: str):
    return history_service.add_reasoning_entry(message_id, content)


def get_reasoning_by_message_id(message_id: str):
    return history_service.get_reasoning_by_message_id(message_id)


def _serialize_history_rows(rows):
    serialized = []
    for r in rows:
        serialized.append(
            {
                "id": r.id,
                "role": r.role,
                "content": _merge_reasoning(r),
                "timestamp": (
                    r.timestamp.isoformat()
                    if hasattr(r.timestamp, "isoformat")
                    else str(r.timestamp)
                ),
                "media": serialize_media_entries(getattr(r, "media", [])),
                "tags": json.loads(getattr(r, "tags", "[]") or "[]"),
            }
        )
    return serialized


def _merge_reasoning(history_row) -> str:
    content = history_row.content or ""
    reasoning_entity = getattr(history_row, "reasoning", None)

    if reasoning_entity:
        reasoning_text = (reasoning_entity.content or "").strip()
        if reasoning_text:
            return f"<think>\n{reasoning_text}\n</think>\n\n{content}"

    return content
