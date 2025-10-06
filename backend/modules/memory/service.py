"""Memory module: encapsulates retrieval of conversational context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from services import database_service
from services.config_service import get_config_value
from services.logger_service import AuditStatus, log_audit_entry
from modules.memory.embeddings import Provider, get_embedding, get_embeddings
from modules.memory import lorebook
from modules.memory.short_term import (
    ShortTermRecord,
    find_matching_record,
    load_recent_records,
)

DEFAULT_RECENT_LIMIT = 32
DEFAULT_THRESHOLD = 0.7
DEFAULT_SESSION_WINDOW = "day"
DEFAULT_EMBED_PROVIDER = Provider.AUTO
DEFAULT_EMBED_MODEL = "nomic-embed-text"
DEFAULT_FALLBACK_MESSAGE = "За сегодня ничего не найдено."
SHORT_TERM_LOOKBACK_DAYS = 7


@dataclass
class MemoryMatch:
    message_id: str
    role: str
    content: str
    timestamp: str
    score: float
    source: str = "recent"

    def formatted(self) -> str:
        role = "User" if self.role == "user" else "Assistant"
        ts = self.timestamp
        return f"{role} ({ts}): {self.content}" if ts else f"{role}: {self.content}"


@dataclass
class MemoryContextResult:
    context: Dict[str, Any]
    meta: Dict[str, Any] = field(default_factory=dict)


def _cosine_similarity(vec_a: Sequence[float], vec_b: Sequence[float]) -> float:
    dot = sum(a * b for a, b in zip(vec_a, vec_b))
    mag_a = sum(a * a for a in vec_a) ** 0.5
    mag_b = sum(b * b for b in vec_b) ** 0.5
    if mag_a == 0 or mag_b == 0:
        return 0.0
    return dot / (mag_a * mag_b)


class MemoryModule:
    """High-level orchestration for conversational memory retrieval."""

    async def collect_context(
        self, input_text: str, message_payload: Dict[str, Any]
    ) -> MemoryContextResult:
        print("[Memory] Модуль запущен, готовим сбор контекста.")
        settings = self._load_settings()
        char_name = get_config_value("char_name", "default_waifu")
        content = (input_text or "").strip()
        meta: Dict[str, Any] = {
            "settings": settings,
            "character": char_name,
        }

        log_audit_entry(
            "memory_module.start",
            "[Memory] Запрос на поиск контекста",
            AuditStatus.INFO,
            details={
                "character": char_name,
                "has_content": bool(content),
                "message_id": message_payload.get("id"),
            },
        )

        if not content:
            print("[Memory] Пустой ввод, возвращаем заглушку.")
            log_audit_entry(
                "memory_module.empty_input",
                "[Memory] Пустой ввод. Пропускаю поиск",
                AuditStatus.WARNING,
                details={"character": char_name},
            )
            return MemoryContextResult(
                context={
                    "key_facts": [DEFAULT_FALLBACK_MESSAGE],
                    "session_length": 0,
                    "memory_status": "empty_input",
                },
                meta=meta,
            )

        user_embedding = get_embedding(
            content,
            provider=settings["embedding_provider"],
            model=settings["embedding_model"],
        )

        if not user_embedding:
            print("[Memory] Не удалось получить эмбеддинг, возвращаем заглушку.")
            log_audit_entry(
                "memory_module.embedding_failed",
                "[Memory] Не удалось получить эмбеддинг пользовательского ввода",
                AuditStatus.ERROR,
                details={"character": char_name},
            )
            return MemoryContextResult(
                context={
                    "key_facts": [DEFAULT_FALLBACK_MESSAGE],
                    "session_length": 0,
                    "memory_status": "embedding_failed",
                },
                meta=meta,
            )

        matches: List[MemoryMatch] = []
        statuses: List[str] = []
        seen_ids: set[str] = set()

        recent_match, recent_count = self._search_recent_history(
            char_name, user_embedding, seen_ids, settings
        )
        meta["recent_evaluated"] = recent_count
        if recent_match:
            print("[Memory] Найдено совпадение в недавних сообщениях.")
            matches.append(recent_match)
            statuses.append(recent_match.source)
            self._log_memory_hit(recent_match)

        session_match = None
        if not matches and settings["session_enabled"]:
            session_match, session_count = self._search_session_history(
                char_name,
                user_embedding,
                seen_ids,
                settings,
                message_payload.get("timestamp"),
            )
            meta["session_evaluated"] = session_count
            if session_match:
                print("[Memory] Найдено совпадение в пределах сессии.")
                matches.append(session_match)
                statuses.append(session_match.source)
                self._log_memory_hit(session_match)

        short_term_payload: Optional[Dict[str, Any]] = None
        if not matches:
            short_match, short_payload = self._search_short_term_memory(
                user_embedding,
                seen_ids,
                settings,
            )
            if short_payload:
                record: ShortTermRecord = short_payload["record"]
                meta.update(
                    {
                        "short_term_record_id": record.id,
                        "short_term_themes": record.themes,
                        "short_term_dialogues": len(record.dialogue_ids),
                    }
                )
            if short_match:
                print("[Memory] Найдено совпадение в краткосрочной памяти.")
                matches.append(short_match)
                statuses.append(short_match.source)
                self._log_memory_hit(short_match)
                short_term_payload = {
                    "summary": short_payload["record"].summary,
                    "themes": short_payload["record"].themes,
                    "dialogue_ids": short_payload["record"].dialogue_ids,
                    "dialogue_preview": [
                        entry["content"] for entry in short_payload["dialogues"][:5]
                    ],
                }
            elif short_payload:
                print("[Memory] Найдена дневная сводка, но релевантных сообщений нет.")
                log_audit_entry(
                    "memory_module.short_term_no_dialogue_match",
                    "[Memory] Краткосрочная память не дала точного совпадения.",
                    AuditStatus.INFO,
                    details={
                        "record_id": short_payload["record"].id,
                        "themes": short_payload["record"].themes,
                    },
                )

        key_facts = [match.formatted() for match in matches]
        if not key_facts:
            key_facts = [DEFAULT_FALLBACK_MESSAGE]

        lore_context = self._collect_lore_context(content)

        context: Dict[str, Any] = {
            "key_facts": key_facts,
            "memory_status": statuses[-1] if statuses else "not_found",
            "session_length": len(matches),
            "matches": [
                {
                    "message_id": match.message_id,
                    "role": match.role,
                    "timestamp": match.timestamp,
                    "score": round(match.score, 4),
                    "source": match.source,
                    "content": match.content,
                }
                for match in matches
            ],
        }

        if short_term_payload:
            context.update(
                {
                    "short_term_summary": short_term_payload["summary"],
                    "short_term_themes": short_term_payload["themes"],
                    "short_term_dialogue_ids": short_term_payload["dialogue_ids"],
                    "short_term_dialogue_preview": short_term_payload["dialogue_preview"],
                    "short_term_record_id": meta.get("short_term_record_id"),
                }
            )

        context.update(lore_context)

        meta.update(
            {
                "matches_found": len(matches),
                "lore_count": lore_context.get("count", 0),
            }
        )

        log_audit_entry(
            "memory_module.result_prepared",
            "[Memory] Контекст готов.",
            AuditStatus.INFO,
            details={
                "matches": context["matches"],
                "short_term_present": bool(short_term_payload),
                "lore_count": lore_context.get("count", 0),
            },
        )
        print("[Memory] Контекст собран и возвращается вызывающей стороне.")

        return MemoryContextResult(context=context, meta=meta)

    async def collect_lore_context(self, text: str) -> Dict[str, Any]:
        """Backward-compatible wrapper for lore-only requests."""
        return self._collect_lore_context(text)

    def _collect_lore_context(self, text: str) -> Dict[str, Any]:
        try:
            threshold = float(get_config_value("lorebook.similarityThreshold", 0.7))
            top_k = int(get_config_value("lorebook.topK", 3))

            log_audit_entry(
                "memory_module.lore_query",
                "[Memory] Выполняю поиск по лорбуку",
                AuditStatus.INFO,
                details={"threshold": threshold, "top_k": top_k},
            )

            entries = lorebook.search_entries(
                query=text,
                top_k=top_k,
                min_similarity=threshold,
            )

            formatted = []
            for entry in entries:
                title = entry.get("title") or ""
                content = entry.get("content") or ""
                phrase = f"{title}: {content}" if title else content
                if phrase:
                    formatted.append(phrase)

            lore_block = "\n".join(
                f"• {item}" for item in formatted
            ) if formatted else ""

            log_audit_entry(
                "memory_module.lore_success",
                "[Memory] Лор найден",
                AuditStatus.SUCCESS,
                details={"count": len(formatted)},
            )

            return {
                "lore_matches": formatted,
                "lore_block": lore_block,
                "count": len(formatted),
                "raw_lore_entries": entries,
            }

        except Exception as exc:  # pragma: no cover
            log_audit_entry(
                "memory_module.lore_error",
                "[Memory] Ошибка поиска по лорбуку",
                AuditStatus.ERROR,
                details={"error": str(exc)},
            )
            return {"lore_matches": [], "lore_block": "", "count": 0, "raw_lore_entries": []}

    def _load_settings(self) -> Dict[str, Any]:
        return {
            "recent_limit": int(get_config_value("memory.recent_limit", DEFAULT_RECENT_LIMIT)),
            "similarity_threshold": float(
                get_config_value("memory.similarity_threshold", DEFAULT_THRESHOLD)
            ),
            "session_window": get_config_value("memory.session_window", DEFAULT_SESSION_WINDOW),
            "session_enabled": bool(
                get_config_value("memory.session_enabled", True)
            ),
            "embedding_provider": (
                get_config_value("memory.embedding_provider", DEFAULT_EMBED_PROVIDER)
                or DEFAULT_EMBED_PROVIDER
            ),
            "embedding_model": (
                get_config_value("memory.embedding_model", DEFAULT_EMBED_MODEL)
                or DEFAULT_EMBED_MODEL
            ),
        }

    def _search_recent_history(
        self,
        character: str,
        user_embedding: List[float],
        seen_ids: set[str],
        settings: Dict[str, Any],
    ) -> Tuple[Optional[MemoryMatch], int]:
        recent_limit = settings["recent_limit"]
        threshold = settings["similarity_threshold"]
        provider = settings["embedding_provider"]
        model = settings["embedding_model"]

        recent_messages = database_service.get_history(character, limit=recent_limit)
        if not recent_messages:
            return None, 0

        log_audit_entry(
            "memory_module.recent_search",
            "[Memory] Поиск в последних сообщениях",
            AuditStatus.INFO,
            details={"count": len(recent_messages), "threshold": threshold},
        )

        match = self._find_best_match(
            recent_messages,
            user_embedding,
            threshold,
            provider,
            model,
            source="recent",
            seen_ids=seen_ids,
        )
        return match, len(recent_messages)

    def _search_session_history(
        self,
        character: str,
        user_embedding: List[float],
        seen_ids: set[str],
        settings: Dict[str, Any],
        timestamp: Optional[str],
    ) -> Tuple[Optional[MemoryMatch], int]:
        start_time = self._compute_session_start(timestamp, settings["session_window"])
        session_messages = database_service.get_history_since(character, start_time)
        if not session_messages:
            return None, 0

        log_audit_entry(
            "memory_module.session_search",
            "[Memory] Поиск в пределах сессии",
            AuditStatus.INFO,
            details={
                "messages": len(session_messages),
                "start_time": start_time,
                "threshold": settings["similarity_threshold"],
            },
        )

        match = self._find_best_match(
            session_messages,
            user_embedding,
            settings["similarity_threshold"],
            settings["embedding_provider"],
            settings["embedding_model"],
            source="session",
            seen_ids=seen_ids,
        )
        return match, len(session_messages)

    def _search_short_term_memory(
        self,
        user_embedding: List[float],
        seen_ids: set[str],
        settings: Dict[str, Any],
    ) -> Tuple[Optional[MemoryMatch], Optional[Dict[str, Any]]]:
        records = load_recent_records(SHORT_TERM_LOOKBACK_DAYS)
        if not records:
            return None, None

        record = find_matching_record(
            user_embedding,
            records,
            threshold=settings["similarity_threshold"],
        )
        if not record:
            return None, None

        history_rows = database_service.get_history_by_ids(record.dialogue_ids)
        if not history_rows:
            return None, {"record": record, "dialogues": []}

        payload = [self._prepare_history_payload(row) for row in history_rows]
        match = self._find_best_match(
            payload,
            user_embedding,
            settings["similarity_threshold"],
            settings["embedding_provider"],
            settings["embedding_model"],
            source="short_term",
            seen_ids=seen_ids,
        )
        return match, {"record": record, "dialogues": payload}

    def _prepare_history_payload(self, row: Any) -> Dict[str, Any]:
        timestamp = (
            row.timestamp.isoformat()
            if hasattr(row, "timestamp") and row.timestamp
            else ""
        )
        return {
            "id": getattr(row, "id", ""),
            "role": getattr(row, "role", "assistant"),
            "content": getattr(row, "content", ""),
            "timestamp": timestamp,
        }

    def _log_memory_hit(self, match: MemoryMatch) -> None:
        preview = (match.content or "").strip()
        if len(preview) > 300:
            preview_display = preview[:297] + "..."
        else:
            preview_display = preview
        print(f"[Memory] Совпадение ({match.source}) → {preview_display}")
        log_audit_entry(
            "memory_module.match_found",
            "[Memory] Найдено совпадение в памяти.",
            AuditStatus.SUCCESS,
            details={
                "source": match.source,
                "message_id": match.message_id,
                "score": round(match.score, 4),
                "content": preview,
            },
        )


    def _find_best_match(
        self,
        messages: Iterable[Dict[str, Any]],
        user_embedding: List[float],
        threshold: float,
        provider: str,
        model: str,
        *,
        source: str,
        seen_ids: set[str],
    ) -> Optional[MemoryMatch]:
        texts: List[str] = []
        mapping: List[Dict[str, Any]] = []
        for msg in messages:
            msg_id = msg.get("id")
            content = (msg.get("content") or "").strip()
            if not content or (msg_id and msg_id in seen_ids):
                continue
            texts.append(content)
            mapping.append(msg)
            if msg_id:
                seen_ids.add(msg_id)

        if not texts:
            return None

        embeddings = get_embeddings(texts, provider=provider, model=model)
        best: Optional[MemoryMatch] = None
        for msg, emb in zip(mapping, embeddings):
            if not emb:
                continue
            score = _cosine_similarity(user_embedding, emb)
            if score < threshold:
                continue
            if best is None or score > best.score:
                best = MemoryMatch(
                    message_id=msg.get("id", ""),
                    role=msg.get("role", "assistant"),
                    content=msg.get("content", ""),
                    timestamp=msg.get("timestamp", ""),
                    score=score,
                    source=source,
                )

        return best

    @staticmethod
    def _compute_session_start(timestamp: Optional[str], window: str) -> str:
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except Exception:
                dt = datetime.now(timezone.utc)
        else:
            dt = datetime.now(timezone.utc)

        if window == "day":
            dt = dt.replace(hour=0, minute=0, second=0, microsecond=0)

        return dt.isoformat()

