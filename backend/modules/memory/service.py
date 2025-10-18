"""Memory module: encapsulates retrieval of conversational context."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import math
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

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
DEFAULT_KEYWORD_MAX_CANDIDATES = 8
DEFAULT_KEYWORD_MIN_SCORE = 0.15
DEFAULT_KEYWORD_MIN_OVERLAP = 0.2
DEFAULT_VECTOR_TOP_K = 8
DEFAULT_VECTOR_THRESHOLD = 0.9
DEFAULT_RERANK_TOP_N = 5
DEFAULT_RERANK_WEIGHT_EMBEDDING = 0.7
DEFAULT_RERANK_WEIGHT_KEYWORD = 0.2
DEFAULT_RERANK_WEIGHT_SHORT_TERM = 0.1
DEFAULT_RERANK_BOOST_RECENCY = 0.0
DEFAULT_KEYWORD_STOPWORDS: Set[str] = {
    "это",
    "как",
    "или",
    "если",
    "when",
    "then",
    "with",
    "что",
    "and",
    "the",
}
DEFAULT_SHORT_TERM_THRESHOLD = 0.75
DEFAULT_HISTORY_LIMIT = 20


@dataclass
class MemoryMatch:
    message_id: str
    role: str
    content: str
    timestamp: str
    score: float
    source: str = "recent"
    details: Dict[str, Any] = field(default_factory=dict)

    def formatted(self) -> str:
        role = "User" if self.role == "user" else "Assistant"
        ts = self.timestamp
        return f"{role} ({ts}): {self.content}" if ts else f"{role}: {self.content}"


@dataclass
class MemoryContextResult:
    context: Dict[str, Any]
    meta: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CandidateEntry:
    payload: Dict[str, Any]
    scores: Dict[str, float] = field(default_factory=dict)
    sources: Set[str] = field(default_factory=set)
    extras: Dict[str, Any] = field(default_factory=dict)
    embeddings: Dict[str, List[float]] = field(default_factory=dict)


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
        print("[Memory] Модуль запущен, выполняем гибридный поиск.")
        settings = self._load_settings()
        char_name = get_config_value("system.char_name", "default_waifu")
        content = (input_text or "").strip()
        meta: Dict[str, Any] = {
            "character": char_name,
            "retrieval_settings": settings["retrieval"],
        }

        history_limit = self._resolve_history_limit()
        history_preview = self._load_history_preview(char_name, history_limit)
        meta["history_preview"] = {
            "limit": history_limit,
            "count": len(history_preview),
        }

        log_audit_entry(
            "memory_module.start",
            "[Memory] Гибридный поиск по памяти.",
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
                "[Memory] Пустой ввод. Пропускаю поиск.",
                AuditStatus.WARNING,
                details={"character": char_name},
            )
            return MemoryContextResult(
                context={
                    "key_facts": [DEFAULT_FALLBACK_MESSAGE],
                    "session_length": 0,
                    "memory_status": "empty_input",
                    "matches": [],
                },
                meta=meta,
            )

        query_vectors = self._compute_query_vectors(content, settings["vectors"])
        has_vectors = any(vec is not None for vec in query_vectors.values())
        if not has_vectors and not settings["retrieval"]["keyword"]["enabled"]:
            print("[Memory] Нет доступных эмбеддингов и keyword-поиск отключен.")
            log_audit_entry(
                "memory_module.embedding_failed",
                "[Memory] Эмбеддинги недоступны, пропускаю поиск.",
                AuditStatus.ERROR,
                details={"character": char_name},
            )
            return MemoryContextResult(
                context={
                    "key_facts": [DEFAULT_FALLBACK_MESSAGE],
                    "session_length": 0,
                    "memory_status": "embedding_failed",
                    "matches": [],
                },
                meta=meta,
            )

        recent_payloads = self._load_recent_messages(char_name, settings["recent_limit"])
        session_payloads = self._load_session_messages(
            char_name,
            message_payload.get("timestamp"),
            settings["session"],
        )
        candidate_payloads = self._merge_payloads(recent_payloads, session_payloads)

        candidate_map: Dict[str, CandidateEntry] = {}

        if candidate_payloads:
            if settings["retrieval"]["keyword"]["enabled"]:
                self._apply_keyword_candidates(
                    content,
                    candidate_payloads,
                    settings["retrieval"]["keyword"],
                    candidate_map,
                )

            for vector_name, vector_cfg in settings["vectors"].items():
                if not vector_cfg["enabled"]:
                    continue
                query_vec = query_vectors.get(vector_name)
                if query_vec is None:
                    continue
                self._apply_vector_candidates(
                    vector_name,
                    vector_cfg,
                    query_vec,
                    candidate_payloads,
                    candidate_map,
                )
        else:
            print("[Memory] Нет кандидатов в недавней/сессионной истории.")

        short_term_meta: Dict[str, Any] = {}
        if settings["short_term"]["enabled"]:
            primary_vector_name = settings["primary_vector"]
            if primary_vector_name:
                primary_vector = query_vectors.get(primary_vector_name)
                vector_cfg = settings["vectors"].get(primary_vector_name)
            else:
                primary_vector = None
                vector_cfg = None

            short_match, short_payload, short_meta = self._search_short_term_memory(
                primary_vector,
                vector_cfg,
                settings["short_term"],
            )
            if short_match and short_payload:
                self._register_candidate(
                    candidate_map,
                    short_payload,
                    score_key="short_term",
                    score_value=short_match.score,
                    source_label="short_term",
                    extras={"record_id": short_meta.get("record_id") if short_meta else None},
                )
                short_term_meta = short_meta or {}

        matches = self._rerank_candidates(
            candidate_map,
            settings,
            query_vectors=query_vectors,
        )

        for match in matches:
            self._log_memory_hit(match)

        lore_context = self._collect_lore_context(content)

        if not matches:
            print("[Memory] Совпадений не найдено, возвращаем fallback.")
            context = {
                "key_facts": [DEFAULT_FALLBACK_MESSAGE],
                "session_length": 0,
                "memory_status": "not_found",
                "matches": [],
            }
            context.update(lore_context)
            context["recent_history"] = history_preview
            meta.update(
                {
                    "matches_found": 0,
                    "lore_count": lore_context.get("count", 0),
                    "history_preview_count": len(history_preview),
                }
            )
            return MemoryContextResult(context=context, meta=meta)

        key_facts = [match.formatted() for match in matches]
        context_matches = [
            {
                "message_id": match.message_id,
                "role": match.role,
                "timestamp": match.timestamp,
                "score": round(match.score, 4),
                "source": match.source,
                "content": match.content,
                "details": match.details,
            }
            for match in matches
        ]

        context: Dict[str, Any] = {
            "key_facts": key_facts,
            "memory_status": "ready",
            "session_length": len(matches),
            "matches": context_matches,
        }

        if short_term_meta:
            context["short_term_record_id"] = short_term_meta.get("record_id")
            context["short_term_dialogue_ids"] = short_term_meta.get("dialogue_ids")

        context.update(lore_context)
        context["recent_history"] = history_preview

        meta.update(
            {
                "matches_found": len(matches),
                "lore_count": lore_context.get("count", 0),
                "short_term_meta": short_term_meta,
                "history_preview_count": len(history_preview),
            }
        )

        log_audit_entry(
            "memory_module.result_prepared",
            "[Memory] Контекст готов (гибридный поиск).",
            AuditStatus.INFO,
            details={
                "match_count": len(matches),
                "short_term_present": bool(short_term_meta),
                "lore_count": lore_context.get("count", 0),
                "history_preview_count": len(history_preview),
            },
        )
        print("[Memory] Контекст собран и возвращается вызывающей стороне.")

        return MemoryContextResult(context=context, meta=meta)

    async def collect_lore_context(self, text: str) -> Dict[str, Any]:
        """Backward-compatible wrapper for lore-only requests."""
        return self._collect_lore_context(text)

    def _collect_lore_context(self, text: str) -> Dict[str, Any]:
        try:
            lore_cfg = get_config_value("rag.lore", {}) or {}
            threshold = float(
                lore_cfg.get(
                    "similarity_threshold",
                    get_config_value("lorebook.similarityThreshold", 0.7),
                )
            )
            top_k = int(
                lore_cfg.get(
                    "top_k",
                    get_config_value("lorebook.topK", 3),
                )
            )

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
        rag_cfg = get_config_value("rag", {}) or {}
        retrieval_raw = rag_cfg.get("retrieval") if isinstance(rag_cfg, dict) else {}
        retrieval_cfg = retrieval_raw if isinstance(retrieval_raw, dict) else {}
        vectors_raw = retrieval_cfg.get("vectors") if isinstance(retrieval_cfg, dict) else {}
        vectors_cfg = vectors_raw if isinstance(vectors_raw, dict) else {}
        profiles_raw = vectors_cfg.get("profiles") if isinstance(vectors_cfg, dict) else {}
        profiles_cfg = profiles_raw if isinstance(profiles_raw, dict) else {}

        vector_settings: Dict[str, Dict[str, Any]] = {}
        for name, profile in profiles_cfg.items():
            if not isinstance(profile, dict):
                continue
            profile_data = dict(profile or {})
            enabled = bool(profile_data.get("enabled", True))
            provider = profile_data.get("provider") or DEFAULT_EMBED_PROVIDER
            model = profile_data.get("model") or DEFAULT_EMBED_MODEL
            top_k = int(profile_data.get("top_k", DEFAULT_VECTOR_TOP_K))
            threshold = float(profile_data.get("threshold", DEFAULT_VECTOR_THRESHOLD))
            label = profile_data.get("label", name)

            profile_data["enabled"] = enabled
            profile_data["provider"] = provider
            profile_data["model"] = model
            profile_data["top_k"] = top_k
            profile_data["threshold"] = threshold
            profile_data["label"] = label
            profile_data["name"] = name

            vector_settings[name] = profile_data

        if not vector_settings:
            default_provider = (
                get_config_value("memory.embedding_provider", DEFAULT_EMBED_PROVIDER)
                or DEFAULT_EMBED_PROVIDER
            )
            default_model = (
                get_config_value("memory.embedding_model", DEFAULT_EMBED_MODEL)
                or DEFAULT_EMBED_MODEL
            )
            vector_settings["default"] = {
                "enabled": True,
                "provider": default_provider,
                "model": default_model,
                "top_k": DEFAULT_VECTOR_TOP_K,
                "threshold": DEFAULT_VECTOR_THRESHOLD,
                "label": "Default",
                "name": "default",
            }

        primary_vector = vectors_cfg.get("primary")
        if (
            not primary_vector
            or primary_vector not in vector_settings
            or not vector_settings[primary_vector]["enabled"]
        ):
            primary_vector = next(
                (
                    name
                    for name, cfg in vector_settings.items()
                    if cfg.get("enabled")
                ),
                next(iter(vector_settings)),
            )

        keyword_raw = retrieval_cfg.get("keyword") if isinstance(retrieval_cfg, dict) else {}
        keyword_cfg = keyword_raw if isinstance(keyword_raw, dict) else {}
        keyword_settings = {
            "enabled": bool(keyword_cfg.get("enabled", True)),
            "max_candidates": int(
                keyword_cfg.get("max_candidates", DEFAULT_KEYWORD_MAX_CANDIDATES)
            ),
            "min_score": float(
                keyword_cfg.get("min_score", DEFAULT_KEYWORD_MIN_SCORE)
            ),
            "min_overlap": float(
                keyword_cfg.get("min_overlap", DEFAULT_KEYWORD_MIN_OVERLAP)
            ),
            "stopwords": list(keyword_cfg.get("stopwords", DEFAULT_KEYWORD_STOPWORDS)),
            "boost_user": float(keyword_cfg.get("boost_user", 1.0)),
            "boost_assistant": float(keyword_cfg.get("boost_assistant", 0.9)),
        }

        rerank_raw = retrieval_cfg.get("rerank") if isinstance(retrieval_cfg, dict) else {}
        rerank_cfg = rerank_raw if isinstance(rerank_raw, dict) else {}
        weights_raw = rerank_cfg.get("weights") if isinstance(rerank_cfg, dict) else {}
        weights_cfg = weights_raw if isinstance(weights_raw, dict) else {}
        rerank_settings = {
            "enabled": bool(rerank_cfg.get("enabled", True)),
            "top_n": int(rerank_cfg.get("top_n", DEFAULT_RERANK_TOP_N)),
            "weights": {
                "embedding": float(
                    weights_cfg.get("embedding", DEFAULT_RERANK_WEIGHT_EMBEDDING)
                ),
                "keyword": float(
                    weights_cfg.get("keyword", DEFAULT_RERANK_WEIGHT_KEYWORD)
                ),
                "short_term": float(
                    weights_cfg.get("short_term", DEFAULT_RERANK_WEIGHT_SHORT_TERM)
                ),
            },
            "boost_recency": float(
                rerank_cfg.get("boost_recency", DEFAULT_RERANK_BOOST_RECENCY)
            ),
            "use_primary_rerank": bool(rerank_cfg.get("use_primary_rerank", True)),
        }

        short_term_raw = retrieval_cfg.get("short_term") if isinstance(retrieval_cfg, dict) else {}
        short_term_cfg = short_term_raw if isinstance(short_term_raw, dict) else {}
        short_term_settings = {
            "enabled": bool(short_term_cfg.get("enabled", True)),
            "threshold": float(
                short_term_cfg.get("threshold", DEFAULT_SHORT_TERM_THRESHOLD)
            ),
        }

        session_raw = retrieval_cfg.get("session") if isinstance(retrieval_cfg, dict) else {}
        session_cfg = session_raw if isinstance(session_raw, dict) else {}
        session_settings = {
            "enabled": bool(
                session_cfg.get(
                    "enabled",
                    get_config_value("memory.session_enabled", True),
                )
            ),
            "window": session_cfg.get(
                "window",
                get_config_value("memory.session_window", DEFAULT_SESSION_WINDOW),
            ),
        }

        recent_raw = retrieval_cfg.get("recent") if isinstance(retrieval_cfg, dict) else {}
        recent_cfg = recent_raw if isinstance(recent_raw, dict) else {}
        recent_limit = int(
            recent_cfg.get(
                "limit",
                get_config_value("memory.recent_limit", DEFAULT_RECENT_LIMIT),
            )
        )

        retrieval_settings = {
            "keyword": keyword_settings,
            "rerank": rerank_settings,
            "vectors": {
                "primary": primary_vector,
                "profiles": {
                    name: {
                        key: value
                        for key, value in cfg.items()
                        if key != "name"
                    }
                    for name, cfg in vector_settings.items()
                },
            },
            "short_term": short_term_settings,
            "recent_limit": recent_limit,
            "session": session_settings,
        }

        return {
            "recent_limit": recent_limit,
            "vectors": vector_settings,
            "primary_vector": primary_vector,
            "retrieval": retrieval_settings,
            "session": session_settings,
            "short_term": short_term_settings,
        }

    def _search_short_term_memory(
        self,
        user_embedding: Optional[List[float]],
        vector_cfg: Optional[Dict[str, Any]],
        short_term_cfg: Dict[str, Any],
    ) -> Tuple[Optional[MemoryMatch], Optional[Dict[str, Any]], Dict[str, Any]]:
        if user_embedding is None or not vector_cfg:
            return None, None, {}

        records = load_recent_records(SHORT_TERM_LOOKBACK_DAYS)
        if not records:
            return None, None, {}

        threshold = float(
            short_term_cfg.get(
                "threshold",
                vector_cfg.get("threshold", DEFAULT_VECTOR_THRESHOLD),
            )
        )
        record = find_matching_record(user_embedding, records, threshold=threshold)
        if not record:
            return None, None, {}

        history_rows = database_service.get_history_by_ids(record.dialogue_ids)
        if not history_rows:
            return None, None, {"record_id": record.id, "dialogue_ids": record.dialogue_ids}

        payloads = [self._prepare_history_payload(row) for row in history_rows]
        match = self._find_best_match(
            payloads,
            user_embedding,
            threshold,
            vector_cfg.get("provider", DEFAULT_EMBED_PROVIDER),
            vector_cfg.get("model", DEFAULT_EMBED_MODEL),
            source="short_term",
            seen_ids=set(),
            vector_cfg=vector_cfg,
        )

        payload_map = {item.get("id"): item for item in payloads if item.get("id")}
        payload_item: Optional[Dict[str, Any]] = None
        if match:
            payload_item = payload_map.get(match.message_id) or (payloads[0] if payloads else None)
            if payload_item is not None:
                match.details = {
                    "source": "short_term",
                    "record_id": record.id,
                    "score": match.score,
                }

        meta = {"record_id": record.id, "dialogue_ids": record.dialogue_ids}
        return match, payload_item, meta

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
        vector_cfg: Optional[Dict[str, Any]] = None,
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

        embeddings = get_embeddings(
            texts,
            provider=provider,
            model=model,
            settings=vector_cfg,
            profile=(vector_cfg or {}).get("name"),
        )
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

    def _compute_query_vectors(
        self,
        content: str,
        vector_settings: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Optional[List[float]]]:
        query_vectors: Dict[str, Optional[List[float]]] = {}
        for name, cfg in vector_settings.items():
            if not cfg.get("enabled"):
                query_vectors[name] = None
                continue

            provider = cfg.get("provider", DEFAULT_EMBED_PROVIDER)
            model = cfg.get("model", DEFAULT_EMBED_MODEL)
            vector = get_embedding(
                content,
                provider=provider,
                model=model,
                settings=cfg,
                profile=cfg.get("name", name),
            )
            query_vectors[name] = vector
        return query_vectors

    def _load_recent_messages(
        self,
        char_name: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        if not char_name:
            return []

        try:
            recent = database_service.get_history(char_name, limit=limit) or []
        except Exception:
            return []

        return list(reversed(recent))

    def _resolve_history_limit(self) -> int:
        raw_limit = get_config_value("rag.history_limit", DEFAULT_HISTORY_LIMIT)
        try:
            limit = int(raw_limit)
        except (TypeError, ValueError):
            limit = DEFAULT_HISTORY_LIMIT
        return max(limit, 0)

    def _load_history_preview(
        self,
        char_name: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        if not char_name or limit <= 0:
            return []

        try:
            history_rows = database_service.get_history(char_name, limit=limit) or []
        except Exception:
            return []

        preview: List[Dict[str, Any]] = []
        for item in reversed(history_rows):
            if not isinstance(item, dict):
                continue
            entry: Dict[str, Any] = {
                "id": item.get("id"),
                "role": item.get("role"),
                "content": item.get("content"),
                "timestamp": item.get("timestamp"),
            }
            media_items = item.get("media")
            if isinstance(media_items, list) and media_items:
                sanitized_media: List[Dict[str, Any]] = []
                for media in media_items:
                    if not isinstance(media, dict):
                        continue
                    sanitized_media.append(
                        {
                            key: value
                            for key, value in media.items()
                            if key.lower() not in {"data", "base64"}
                        }
                    )
                if sanitized_media:
                    entry["media"] = sanitized_media
            preview.append(entry)

        return preview

    def _load_session_messages(
        self,
        char_name: Optional[str],
        timestamp: Optional[str],
        session_cfg: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not char_name or not session_cfg.get("enabled", True):
            return []

        start = self._compute_session_start(timestamp, session_cfg.get("window", DEFAULT_SESSION_WINDOW))
        try:
            payloads = database_service.get_history_since(char_name, start) or []
        except Exception:
            payloads = []
        return payloads

    def _merge_payloads(
        self,
        *payload_groups: Sequence[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        merged: List[Dict[str, Any]] = []
        seen: Set[str] = set()

        for group in payload_groups:
            for payload in group or []:
                if not isinstance(payload, dict):
                    continue
                candidate_id = payload.get("id") or self._make_candidate_id(payload)
                if candidate_id in seen:
                    continue
                seen.add(candidate_id)
                merged.append(payload)

        return merged

    def _apply_keyword_candidates(
        self,
        query: str,
        candidate_payloads: Sequence[Dict[str, Any]],
        keyword_cfg: Dict[str, Any],
        candidate_map: Dict[str, CandidateEntry],
    ) -> None:
        if not keyword_cfg.get("enabled", True):
            return

        stopwords = set(keyword_cfg.get("stopwords", DEFAULT_KEYWORD_STOPWORDS))
        query_tokens = self._tokenize(query, stopwords)
        if not query_tokens:
            return

        scored: List[Tuple[Dict[str, Any], float, Dict[str, Any]]] = []
        for payload in candidate_payloads:
            text = (payload.get("content") or "").strip()
            if not text:
                continue
            payload_tokens = self._tokenize(text, stopwords)
            score, overlap_ratio = self._keyword_match_score(
                query_tokens,
                payload_tokens,
                payload.get("role", ""),
                keyword_cfg,
            )
            if score < keyword_cfg.get("min_score", DEFAULT_KEYWORD_MIN_SCORE):
                continue
            scored.append(
                (
                    payload,
                    score,
                    {
                        "overlap_ratio": overlap_ratio,
                        "token_count": len(payload_tokens),
                    },
                )
            )

        scored.sort(key=lambda item: item[1], reverse=True)
        max_candidates = max(1, int(keyword_cfg.get("max_candidates", DEFAULT_KEYWORD_MAX_CANDIDATES)))

        for payload, score, extras in scored[:max_candidates]:
            self._register_candidate(
                candidate_map,
                payload,
                score_key="keyword",
                score_value=score,
                source_label="keyword",
                extras=extras,
            )

    def _apply_vector_candidates(
        self,
        vector_name: str,
        vector_cfg: Dict[str, Any],
        query_vec: Optional[List[float]],
        candidate_payloads: Sequence[Dict[str, Any]],
        candidate_map: Dict[str, CandidateEntry],
    ) -> None:
        if query_vec is None:
            return

        provider = vector_cfg.get("provider", DEFAULT_EMBED_PROVIDER)
        model = vector_cfg.get("model", DEFAULT_EMBED_MODEL)
        threshold = float(vector_cfg.get("threshold", DEFAULT_VECTOR_THRESHOLD))
        top_k = int(vector_cfg.get("top_k", DEFAULT_VECTOR_TOP_K))

        texts: List[str] = []
        mapping: List[Dict[str, Any]] = []
        for payload in candidate_payloads:
            text = (payload.get("content") or "").strip()
            if not text:
                continue
            texts.append(text)
            mapping.append(payload)

        if not texts:
            return

        profile_name = vector_cfg.get("name", vector_name)
        embeddings = get_embeddings(
            texts,
            provider=provider,
            model=model,
            settings=vector_cfg,
            profile=profile_name,
        )
        scored: List[Tuple[Dict[str, Any], float, Optional[List[float]]]] = []

        for payload, embedding in zip(mapping, embeddings):
            if embedding is None:
                continue
            score = _cosine_similarity(query_vec, embedding)
            if score < threshold:
                continue
            scored.append((payload, score, embedding))

        scored.sort(key=lambda item: item[1], reverse=True)

        for payload, score, embedding in scored[:top_k]:
            self._register_candidate(
                candidate_map,
                payload,
                score_key=f"vector.{vector_name}",
                score_value=score,
                source_label=f"vector:{vector_name}",
                extras={
                    "provider": provider,
                    "model": model,
                    "profile": profile_name,
                },
                embedding_label=vector_name,
                embedding=embedding,
            )

    def _register_candidate(
        self,
        candidate_map: Dict[str, CandidateEntry],
        payload: Dict[str, Any],
        *,
        score_key: str,
        score_value: float,
        source_label: str,
        extras: Optional[Dict[str, Any]] = None,
        embedding_label: Optional[str] = None,
        embedding: Optional[List[float]] = None,
    ) -> None:
        candidate_id = payload.get("id") or self._make_candidate_id(payload)
        entry = candidate_map.get(candidate_id)
        if entry is None:
            entry = CandidateEntry(payload=dict(payload))
            candidate_map[candidate_id] = entry

        previous = entry.scores.get(score_key)
        if previous is None or score_value > previous:
            entry.scores[score_key] = score_value

        entry.sources.add(source_label)

        if extras:
            bucket = entry.extras.setdefault(source_label, {})
            bucket.update(extras)

        if embedding_label and embedding is not None:
            entry.embeddings[embedding_label] = embedding

    def _rerank_candidates(
        self,
        candidate_map: Dict[str, CandidateEntry],
        settings: Dict[str, Any],
        *,
        query_vectors: Dict[str, Optional[List[float]]],
    ) -> List[MemoryMatch]:
        if not candidate_map:
            return []

        rerank_cfg = settings.get("retrieval", {}).get("rerank", {})
        weights_cfg = rerank_cfg.get("weights", {}) if isinstance(rerank_cfg, dict) else {}
        embedding_weight = float(weights_cfg.get("embedding", DEFAULT_RERANK_WEIGHT_EMBEDDING))
        keyword_weight = float(weights_cfg.get("keyword", DEFAULT_RERANK_WEIGHT_KEYWORD))
        short_term_weight = float(weights_cfg.get("short_term", DEFAULT_RERANK_WEIGHT_SHORT_TERM))

        primary_vector = settings.get("primary_vector")
        primary_cfg = settings.get("vectors", {}).get(primary_vector) if primary_vector else None
        primary_query_vec = query_vectors.get(primary_vector) if primary_vector else None

        if (
            rerank_cfg.get("use_primary_rerank", True)
            and primary_vector
            and primary_cfg
            and primary_query_vec is not None
        ):
            missing_entries = [
                entry
                for entry in candidate_map.values()
                if primary_vector not in entry.embeddings
            ]
            if missing_entries:
                texts = [
                    (entry.payload.get("content") or "").strip()
                    for entry in missing_entries
                ]
                embeddings = get_embeddings(
                    texts,
                    provider=primary_cfg.get("provider", DEFAULT_EMBED_PROVIDER),
                    model=primary_cfg.get("model", DEFAULT_EMBED_MODEL),
                    settings=primary_cfg,
                    profile=primary_cfg.get("name", primary_vector),
                )
                for entry, embedding in zip(missing_entries, embeddings):
                    if embedding is not None:
                        entry.embeddings[primary_vector] = embedding

            for entry in candidate_map.values():
                embedding = entry.embeddings.get(primary_vector)
                if embedding is not None and primary_query_vec is not None:
                    entry.scores[f"vector.{primary_vector}.rerank"] = _cosine_similarity(
                        primary_query_vec,
                        embedding,
                    )

        ranked: List[Tuple[CandidateEntry, float]] = []
        recency_boost = float(rerank_cfg.get("boost_recency", DEFAULT_RERANK_BOOST_RECENCY))

        for entry in candidate_map.values():
            embedding_scores = [
                score
                for key, score in entry.scores.items()
                if key.startswith("vector.")
            ]
            embedding_score = max(embedding_scores) if embedding_scores else 0.0
            keyword_score = entry.scores.get("keyword", 0.0)
            short_term_score = entry.scores.get("short_term", 0.0)

            total = (
                embedding_weight * embedding_score
                + keyword_weight * keyword_score
                + short_term_weight * short_term_score
            )

            if recency_boost > 0:
                recency = self._compute_recency_boost(entry.payload.get("timestamp"))
                total += recency_boost * recency

            ranked.append((entry, total))

        ranked.sort(key=lambda item: item[1], reverse=True)
        top_n = max(1, int(rerank_cfg.get("top_n", DEFAULT_RERANK_TOP_N)))

        matches: List[MemoryMatch] = []
        for entry, score in ranked[:top_n]:
            payload = entry.payload
            details = {
                "scores": {k: round(v, 4) for k, v in entry.scores.items()},
                "sources": sorted(entry.sources),
                "meta": entry.extras,
            }
            match = MemoryMatch(
                message_id=payload.get("id", ""),
                role=payload.get("role", "assistant"),
                content=payload.get("content", ""),
                timestamp=payload.get("timestamp", ""),
                score=score,
                source="|".join(sorted(entry.sources)) or "hybrid",
                details=details,
            )
            matches.append(match)

        return matches

    @staticmethod
    def _tokenize(text: str, stopwords: Optional[Set[str]] = None) -> List[str]:
        tokens = [
            token
            for token in re.findall(r"[\w-]{2,}", text.lower())
            if len(token) > 2
        ]
        if stopwords:
            lowered = {s.lower() for s in stopwords}
            tokens = [token for token in tokens if token not in lowered]
        return tokens

    def _keyword_match_score(
        self,
        query_tokens: Sequence[str],
        payload_tokens: Sequence[str],
        role: str,
        keyword_cfg: Dict[str, Any],
    ) -> Tuple[float, float]:
        if not payload_tokens:
            return 0.0, 0.0

        token_set = set(payload_tokens)
        overlap_tokens = [token for token in query_tokens if token in token_set]
        if not overlap_tokens:
            return 0.0, 0.0

        overlap_ratio = len(overlap_tokens) / max(len(query_tokens), 1)
        coverage_ratio = len(overlap_tokens) / max(len(payload_tokens), 1)

        if overlap_ratio < keyword_cfg.get("min_overlap", DEFAULT_KEYWORD_MIN_OVERLAP):
            return 0.0, overlap_ratio

        score = (overlap_ratio * 0.7) + (coverage_ratio * 0.3)
        if role == "user":
            score *= float(keyword_cfg.get("boost_user", 1.0))
        else:
            score *= float(keyword_cfg.get("boost_assistant", 0.9))

        return score, overlap_ratio

    @staticmethod
    def _make_candidate_id(payload: Dict[str, Any]) -> str:
        basis = "::".join(
            [
                payload.get("role", ""),
                payload.get("timestamp", ""),
                (payload.get("content", "") or "")[:120],
            ]
        )
        return hashlib.sha1(basis.encode("utf-8", "ignore")).hexdigest()

    @staticmethod
    def _compute_recency_boost(timestamp: Optional[str]) -> float:
        dt = MemoryModule._parse_timestamp(timestamp)
        if not dt:
            return 0.0

        now = datetime.now(timezone.utc)
        delta = now - dt
        hours = max(delta.total_seconds() / 3600.0, 0.0)
        return math.exp(-hours / 24.0)

    @staticmethod
    def _parse_timestamp(timestamp: Optional[str]) -> Optional[datetime]:
        if not timestamp:
            return None
        try:
            return datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        except Exception:
            return None

