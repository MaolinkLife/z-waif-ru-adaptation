"""Short-term memory helpers: schema management, summarization, retrieval."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Sequence

from sqlalchemy import text
from sqlalchemy.orm import Session

from models.models import History, ShortTermMemory
from services.db_core import engine, SessionLocal
from services.logger_service import AuditStatus, log_audit_entry
from services.localization_service import get_text
from services.config_service import get_config_value

from modules.generative.manager import generation_manager, NoProviderResolved
from modules.generative.types import GenerateRequest
from modules.memory.embeddings import Provider, get_embedding

DEFAULT_SIMILARITY_THRESHOLD = 0.7


def _get_primary_vector_profile() -> dict:
    retrieval_cfg = get_config_value("rag.retrieval", {}) or {}
    vectors_cfg = retrieval_cfg.get("vectors", {}) if isinstance(retrieval_cfg, dict) else {}
    profiles_cfg = vectors_cfg.get("profiles", {}) if isinstance(vectors_cfg, dict) else {}
    primary_name = vectors_cfg.get("primary")
    if primary_name and isinstance(profiles_cfg, dict) and primary_name in profiles_cfg:
        profile = dict(profiles_cfg.get(primary_name) or {})
        profile.setdefault("name", primary_name)
        return profile

    if isinstance(profiles_cfg, dict):
        for name, cfg in profiles_cfg.items():
            profile = dict(cfg or {})
            profile.setdefault("name", name)
            return profile
    return {}


@dataclass
class ShortTermRecord:
    id: str
    summary: str
    dialogue_ids: List[str]
    themes: List[str]
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

def _execute_sql(statement: str) -> None:
    with engine.connect() as connection:
        connection.execute(text(statement))
        connection.commit()


def ensure_short_term_schema() -> None:
    print(
        get_text(
            "short_memory.print_schema_check",
            default="[ShortTermMemory] Запущен модуль проверки схемы.",
        )
    )
    log_audit_entry(
        "short_memory_schema_check",
        get_text(
            "logger.short_memory_schema_check",
            default="[ShortTermMemory] Проверяем схему и обязательные поля.",
        ),
        AuditStatus.INFO,
        message_key="logger.short_memory_schema_check",
    )

    with engine.connect() as connection:
        tables = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }

    if "short_term_memory" not in tables:
        print(
            get_text(
                "short_memory.print_create_table",
                default="[ShortTermMemory] Создаём таблицу краткосрочной памяти.",
            )
        )
        ShortTermMemory.__table__.create(bind=engine)
        log_audit_entry(
            "short_memory_table_created",
            get_text(
                "logger.short_memory_table_created",
                default="[ShortTermMemory] Создана таблица краткосрочной памяти.",
            ),
            AuditStatus.SUCCESS,
            message_key="logger.short_memory_table_created",
        )

    _ensure_column("history", "tags", "TEXT DEFAULT '[]'")
    _ensure_column("messages", "tags", "TEXT DEFAULT '[]'")


def _ensure_column(table: str, column: str, ddl: str) -> None:
    with engine.connect() as connection:
        columns = {
            row[1] for row in connection.execute(text(f"PRAGMA table_info({table})"))
        }
    if column in columns:
        return
    print(
        get_text(
            "short_memory.print_add_column",
            params={"column": column, "table": table},
            default=f"[ShortTermMemory] Добавляем колонку {column} в {table}.",
        )
    )
    log_audit_entry(
        "short_memory_column_missing",
        get_text(
            "logger.short_memory_column_missing",
            params={"column": column, "table": table},
            default=f"[ShortTermMemory] Добавление колонки {column} в {table}.",
        ),
        AuditStatus.WARNING,
        message_key="logger.short_memory_column_missing",
        message_args={"column": column, "table": table},
    )
    _execute_sql(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


# ---------------------------------------------------------------------------
# Data preparation
# ---------------------------------------------------------------------------

def refresh_recent_days(
    character_id: str,
    days: int = 7,
    summary_prompt: Optional[str] = None,
) -> None:
    print(
        get_text(
            "short_memory.print_refresh_start",
            default="[ShortTermMemory] Начинаем обновление краткосрочной памяти.",
        )
    )
    log_audit_entry(
        "short_memory_refresh_start",
        get_text(
            "logger.short_memory_refresh_start",
            default="[ShortTermMemory] Запускаем обновление записей за последние дни.",
        ),
        AuditStatus.INFO,
        details={"days": days},
        message_key="logger.short_memory_refresh_start",
    )

    now = datetime.now(timezone.utc)
    session: Session = SessionLocal()

    try:
        for offset in range(days):
            day_start = datetime(
                year=now.year,
                month=now.month,
                day=now.day,
                tzinfo=timezone.utc,
            ) - timedelta(days=offset)
            day_end = day_start + timedelta(days=1)

            existing = (
                session.query(ShortTermMemory)
                .filter(
                    ShortTermMemory.created_at >= day_start,
                    ShortTermMemory.created_at < day_end,
                )
                .first()
            )
            if existing:
                continue

            day_messages = (
                session.query(History)
                .filter(
                    History.character_id == character_id,
                    History.timestamp >= day_start,
                    History.timestamp < day_end,
                )
                .order_by(History.timestamp.asc())
                .all()
            )

            if not day_messages:
                continue

            dialogue_ids = [msg.id for msg in day_messages]
            transcript = _build_transcript(day_messages)
            summary, themes = _generate_day_summary(
                transcript,
                day_start,
                summary_prompt=summary_prompt,
            )

            record = ShortTermMemory(
                summary=summary,
                dialogue_ids=json.dumps(dialogue_ids, ensure_ascii=False),
                themes=json.dumps(themes, ensure_ascii=False),
                created_at=day_start,
            )
            session.add(record)
            session.commit()

            print(
                get_text(
                    "short_memory.print_day_saved",
                    params={
                        "date": str(day_start.date()),
                        "count": len(dialogue_ids),
                    },
                    default=f"[ShortTermMemory] Сохранили сводку за {day_start.date()} по {len(dialogue_ids)} сообщениям.",
                )
            )
            log_audit_entry(
                "short_memory_day_saved",
                get_text(
                    "logger.short_memory_day_saved",
                    default="[ShortTermMemory] Создан дневной блок краткосрочной памяти.",
                ),
                AuditStatus.SUCCESS,
                details={
                    "date": str(day_start.date()),
                    "messages": len(dialogue_ids),
                    "themes": themes,
                },
                message_key="logger.short_memory_day_saved",
            )
    finally:
        session.close()


def _build_transcript(messages: Sequence[History]) -> str:
    lines = []
    for msg in messages:
        role = msg.role.capitalize()
        lines.append(f"{role}: {msg.content}")
    transcript = "\n".join(lines)
    print(
        get_text(
            "short_memory.print_transcript",
            params={"length": len(transcript)},
            default="[ShortTermMemory] Собран транскрипт для суммаризации, длина символов: {length}",
        )
    )
    return transcript


def _generate_day_summary(
    transcript: str,
    day_start: datetime,
    *,
    summary_prompt: Optional[str] = None,
) -> tuple[str, List[str]]:
    summary_prompt = summary_prompt or (
        "Составь краткую выжимку за день и перечисли ключевые темы."
    )

    system_message = {
        "role": "system",
        "content": (
            "Ты помощник, который сжимает беседу за день. Верни JSON с полями "
            "summary (строка) и themes (список из 3-7 коротких тегов, латиницей или "
            "транслитом)."
        ),
    }
    user_message = {
        "role": "user",
        "content": (
            f"Дата: {day_start.date()}\n"
            f"Задача: {summary_prompt}\n"
            "Диалоговые фрагменты:\n"
            f"{transcript[:8000]}"
        ),
    }

    try:
        result = generation_manager.generate(
            GenerateRequest(messages=[system_message, user_message])
        )
        raw = (result.content or "").strip()
        data = json.loads(raw)
        summary = data.get("summary") or raw
        themes = data.get("themes") or []
        themes = [str(t).strip() for t in themes if str(t).strip()]
    except (NoProviderResolved, json.JSONDecodeError, ValueError) as exc:
        log_audit_entry(
            "short_memory_summary_fallback",
            get_text(
                "logger.short_memory_summary_fallback",
                default="[ShortTermMemory] Не удалось получить JSON-резюме, использую fallback.",
            ),
            AuditStatus.WARNING,
            details={"error": str(exc)},
            message_key="logger.short_memory_summary_fallback",
            message_args={"error": str(exc)},
        )
        summary = " ".join(transcript.split("\n")[:5])[:600]
        themes = []

    return summary, themes


# ---------------------------------------------------------------------------
# Retrieval helpers
# ---------------------------------------------------------------------------

def load_recent_records(days: int = 7) -> List[ShortTermRecord]:
    session: Session = SessionLocal()
    now = datetime.now(timezone.utc)
    threshold = now - timedelta(days=days)

    try:
        rows = (
            session.query(ShortTermMemory)
            .filter(ShortTermMemory.created_at >= threshold)
            .order_by(ShortTermMemory.created_at.desc())
            .all()
        )
        records: List[ShortTermRecord] = []
        for row in rows:
            records.append(
                ShortTermRecord(
                    id=row.id,
                    summary=row.summary,
                    dialogue_ids=json.loads(row.dialogue_ids or "[]"),
                    themes=json.loads(row.themes or "[]"),
                    created_at=row.created_at,
                    updated_at=row.updated_at or row.created_at,
                )
            )
        print(
            get_text(
                "short_memory.print_records_loaded",
                params={"count": len(records)},
                default="[ShortTermMemory] Загружено {count} записей краткосрочной памяти.",
            )
        )
        return records
    finally:
        session.close()


def find_matching_record(
    query_embedding: Sequence[float],
    records: Iterable[ShortTermRecord],
    *,
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
) -> Optional[ShortTermRecord]:
    best_record: Optional[ShortTermRecord] = None
    best_score = -math.inf

    profile_cfg = _get_primary_vector_profile()
    provider = profile_cfg.get("provider", get_config_value("memory.embedding_provider", Provider.AUTO))
    model = profile_cfg.get("model") or get_config_value("memory.embedding_model", "nomic-embed-text")

    for record in records:
        record_embedding = get_embedding(
            record.summary,
            provider=provider,
            model=model,
            settings=profile_cfg,
            profile=profile_cfg.get("name"),
        )
        if not record_embedding:
            continue
        score = _cosine_similarity(query_embedding, record_embedding)
        if score >= threshold and score > best_score:
            best_record = record
            best_score = score

    if best_record:
        log_audit_entry(
            "short_memory_match",
            get_text(
                "logger.short_memory_match",
                default="[ShortTermMemory] Найдена релевантная дневная сводка.",
            ),
            AuditStatus.SUCCESS,
            details={
                "record_id": best_record.id,
                "summary_preview": best_record.summary[:120],
                "themes": best_record.themes,
                "score": best_score,
            },
            message_key="logger.short_memory_match",
        )
    else:
        log_audit_entry(
            "short_memory_no_match",
            get_text(
                "logger.short_memory_no_match",
                default="[ShortTermMemory] Релевантная дневная сводка не найдена.",
            ),
            AuditStatus.INFO,
            message_key="logger.short_memory_no_match",
        )

    return best_record


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = math.sqrt(sum(a * a for a in vec_a))
    mag_b = math.sqrt(sum(b * b for b in vec_b))
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


__all__ = [
    "ShortTermRecord",
    "ensure_short_term_schema",
    "refresh_recent_days",
    "load_recent_records",
    "find_matching_record",
]
