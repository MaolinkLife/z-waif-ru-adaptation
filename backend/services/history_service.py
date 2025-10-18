import uuid
from datetime import datetime, timezone
from sqlalchemy.orm import Session, joinedload
from models.models import History, Reasoning
from services.db_core import SessionLocal
from services.logger_service import log_audit_entry, AuditStatus
from utils.time_utils import format_user_datetime
import json
import asyncio
from typing import Optional, Sequence
from services.storage_service import (
    save_media_for_message,
    serialize_media_entries,
    delete_media_files,
)
from modules.generative import conversation
from core.decision_layer import decision_layer


def add_history(
    character_id: str,
    role: str,
    content: str,
    timestamp: Optional[datetime] = None,
    session: Optional[Session] = None,
    media_items: Optional[list] = None,
    tags: Optional[Sequence[str]] = None,
):
    """Добавление сообщения в историю"""
    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True

    try:
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        entry = History(
            id=str(uuid.uuid4()),
            character_id=character_id,
            role=role,
            content=content,
            timestamp=timestamp,
            tags=json.dumps(list(tags or []), ensure_ascii=False),
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)

        media_count_in = len(media_items) if media_items else 0
        log_audit_entry(
            "history_media_received",
            "[History] Incoming media payload.",
            AuditStatus.INFO,
            details={
                "message_id": entry.id,
                "role": role,
                "media_count": media_count_in,
            },
        )

        media_payload = []
        if media_items:
            storage_entries = save_media_for_message(entry.id, media_items)
            media_payload = serialize_media_entries(storage_entries)

        log_audit_entry(
            "history_media_saved",
            "[History] Saved message with media payload.",
            AuditStatus.INFO,
            details={
                "message_id": entry.id,
                "role": role,
                "media_count": len(media_payload),
            },
        )

        entry.media_payload = media_payload
        return entry
    finally:
        if own_session:
            session.close()


def add_reasoning_entry(
    message_id: str,
    content: str,
    session: Optional[Session] = None,
):
    if not content:
        return None

    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True

    try:
        existing = session.query(Reasoning).filter_by(message_id=message_id).first()
        if existing:
            existing.content = content
            session.commit()
            session.refresh(existing)
            return existing

        entry = Reasoning(message_id=message_id, content=content)
        session.add(entry)
        session.commit()
        session.refresh(entry)

        return entry
    finally:
        if own_session:
            session.close()


def get_reasoning_by_message_id(message_id: str) -> Optional[str]:
    session: Session = SessionLocal()
    try:
        entry = session.query(Reasoning).filter_by(message_id=message_id).first()
        return entry.content if entry else None
    finally:
        session.close()


def get_history(character_id: str, limit: int = 20, offset: int = 0):
    """Получение истории сообщений с возможностью смещения (offset)"""
    session: Session = SessionLocal()
    try:
        return (
            session.query(History)
            .options(joinedload(History.reasoning), joinedload(History.media))
            .filter_by(character_id=character_id)
            .order_by(History.timestamp.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
    finally:
        session.close()


def get_history_since(character_id: str, start_time):
    """Возвращает историю сообщений, начиная с указанного времени (включительно)."""
    if isinstance(start_time, str):
        try:
            start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        except Exception:
            start_time = datetime.now(timezone.utc).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
    elif not isinstance(start_time, datetime):
        start_time = datetime.now(timezone.utc).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    session: Session = SessionLocal()
    try:
        return (
            session.query(History)
            .options(joinedload(History.reasoning), joinedload(History.media))
            .filter(
                History.character_id == character_id,
                History.timestamp >= start_time,
            )
            .order_by(History.timestamp.asc())
            .all()
        )
    finally:
        session.close()


def delete_message(message_id: str) -> bool:
    """Удаление одного сообщения по ID"""
    session: Session = SessionLocal()
    try:
        message = (
            session.query(History)
            .options(joinedload(History.reasoning), joinedload(History.media))
            .filter_by(id=message_id)
            .first()
        )
        if not message:
            return False

        delete_media_files(message.media)
        session.delete(message)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"Error deleting message {message_id}: {e}")
        return False
    finally:
        session.close()


def delete_message_chain(user_message_id: str) -> int:
    """Delete a message pair (user + assistant)."""
    session: Session = SessionLocal()
    try:
        # Locate the user message
        user_msg = (
            session.query(History)
            .options(joinedload(History.reasoning), joinedload(History.media))
            .filter_by(id=user_message_id)
            .first()
        )
        if not user_msg or user_msg.role != "user":
            return 0

        # Locate the following assistant reply
        assistant_msg = (
            session.query(History)
            .options(joinedload(History.reasoning), joinedload(History.media))
            .filter(
                History.character_id == user_msg.character_id,
                History.timestamp > user_msg.timestamp,
                History.role == "assistant",
            )
            .order_by(History.timestamp.asc())
            .first()
        )

        count = 0
        delete_media_files(user_msg.media)
        session.delete(user_msg)
        count += 1

        if assistant_msg:
            delete_media_files(assistant_msg.media)
            session.delete(assistant_msg)
            count += 1

        session.commit()
        return count
    except Exception as e:
        session.rollback()
        print(f"Error deleting message chain {user_message_id}: {e}")
        return 0
    finally:
        session.close()


def get_message_by_id(message_id: str):
    """Fetch a message by its ID."""
    session: Session = SessionLocal()
    try:
        message = (
            session.query(History)
            .options(joinedload(History.media))
            .filter_by(id=message_id)
            .first()
        )
        if not message:
            return None

        return {
            "id": message.id,
            "role": message.role,
            "content": message.content,
            "timestamp": format_user_datetime(message.timestamp),
            "character_id": message.character_id,
            "media": serialize_media_entries(message.media),
        }
    finally:
        session.close()


def get_full_history(character_id: str):
    """Fetch the entire conversation history."""
    session: Session = SessionLocal()
    try:
        messages = (
            session.query(History)
            .filter_by(character_id=character_id)
            .order_by(History.timestamp.asc())
            .all()
        )

        return [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "timestamp": format_user_datetime(msg.timestamp),
            }
            for msg in messages
        ]
    finally:
        session.close()


def get_last_user_message_time(character_id: str):
    """Получение времени последнего сообщения пользователя"""
    session: Session = SessionLocal()
    try:
        last_user_msg = (
            session.query(History)
            .filter_by(character_id=character_id, role="user")
            .order_by(History.timestamp.desc())
            .first()
        )

        return last_user_msg.timestamp if last_user_msg else None
    finally:
        session.close()


def get_last_messages(character_id: str, limit: int = 10):
    """Получение последних сообщений"""
    session: Session = SessionLocal()
    try:
        messages = (
            session.query(History)
            .filter_by(character_id=character_id)
            .order_by(History.timestamp.desc())
            .limit(limit)
            .all()
        )

        return [
            {
                "id": msg.id,
                "role": msg.role,
                "content": msg.content,
                "timestamp": format_user_datetime(msg.timestamp),
            }
            for msg in reversed(messages)
        ]
    finally:
        session.close()




def get_messages_by_ids(message_ids: Sequence[str]):
    """Получить сообщения истории по списку идентификаторов."""
    if not message_ids:
        return []
    session: Session = SessionLocal()
    try:
        return (
            session.query(History)
            .filter(History.id.in_(message_ids))
            .order_by(History.timestamp.asc())
            .all()
        )
    finally:
        session.close()

# =========================
# REROLL functionality
# =========================
def get_message_from_database(session, filters: dict, expected_role: str = None):
    """Fetch a message by filters."""
    query = session.query(History).filter_by(**filters)
    result = query.first()

    if not result:
        raise ValueError("Message not found.")

    if expected_role and result.role != expected_role:
        raise ValueError(
            f"Message found, but role '{result.role}' does not match expected '{expected_role}'."
        )

    return result


def get_last_user_message_before(session, character_id, before_timestamp):
    """Get the last user message before a specific timestamp."""
    result = (
        session.query(History)
        .filter(
            History.character_id == character_id,
            History.timestamp < before_timestamp,
            History.role == "user",
        )
        .order_by(History.timestamp.desc())
        .first()
    )

    if not result:
        raise ValueError("No matching user message found.")

    return result


def delete_messages_from_database(session, messages: list):
    """Delete a list of messages within an existing session."""
    try:
        for msg in messages or []:
            delete_media_files(getattr(msg, "media", []))
            session.delete(msg)
        session.commit()
    except Exception as e:
        session.rollback()
        raise


def build_history_up_to_user_message(session, character_id, user_msg, limit=32):
    """Build history up to a given user message."""
    try:
        user_timestamp = user_msg.timestamp

        # Collect the last N messages before the user message
        history_before_user = (
            session.query(History)
            .filter(
                History.character_id == character_id, History.timestamp < user_timestamp
            )
            .order_by(History.timestamp.desc())
            .limit(limit)
            .all()
        )

        # Reverse so that timestamps go forward
        history = [
            {
                "role": msg.role,
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat(),
            }
            for msg in reversed(history_before_user)
        ]

        # Append the user message at the end
        history.append(
            {
                "role": "user",
                "content": user_msg.content,
                "timestamp": user_timestamp.isoformat(),
            }
        )

        return history

    except Exception as e:
        raise


async def reroll_assistant_message(message_id: str) -> dict:
    """Regenerate an assistant message."""
    session: Session = SessionLocal()
    try:

        # 1. Locate the assistant message
        try:
            assistant_msg = get_message_from_database(
                session, filters={"id": message_id}, expected_role="assistant"
            )
        except ValueError as e:
            print(f"[ERROR] Message not found: {e}")
            raise

        assistant_timestamp = assistant_msg.timestamp

        # 2. Locate the paired user message
        user_msg = get_last_user_message_before(
            session,
            character_id=assistant_msg.character_id,
            before_timestamp=assistant_msg.timestamp,
        )

        # 3. Delete the existing messages
        print(
            assistant_msg.id,
            "=>",
            assistant_msg.content[:30],
        )
        delete_messages_from_database(session, [assistant_msg, user_msg])

        # 4. Build history up to the user message
        history = build_history_up_to_user_message(
            session, character_id=user_msg.character_id, user_msg=user_msg, limit=32
        )

        last_user = history[-1] if history else None
        if not last_user or last_user.get("role") != "user":
            raise ValueError("Unable to locate user message for reroll")

        user_message = dict(last_user)
        user_message.setdefault("history", history[:-1])

        decision_context = await decision_layer.process_message(user_message, None)
        decision_context.pop("raw_media", None)
        new_response = await conversation.generate_standard(
            decision_context,
            history,
            user_message,
            return_full=True,
        )

        return {
            "role": "assistant",
            "content": new_response["content"],
            "timestamp": (
                new_response["timestamp"].isoformat()
                if hasattr(new_response["timestamp"], "isoformat")
                else str(new_response["timestamp"])
            ),
            "id": new_response["id"],
        }

    finally:
        session.close()


def get_lorebook_entries(character_name: str):
    """Placeholder: fetch lorebook entries (not implemented)."""
    # TODO: implement lorebook lookup
    return []
