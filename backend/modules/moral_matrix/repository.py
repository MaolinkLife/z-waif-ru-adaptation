"""Database access helpers for the MoralMatrix module."""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import date
from pprint import pformat
from typing import Any, Dict, Iterable, List, Optional, Sequence

from sqlalchemy.orm import Session

from models.models import (
    DailyMoralSummary,
    EmotionalTrace,
    MoralStateSnapshot,
)
from services.db_core import SessionLocal
from services.logger_service import AuditStatus, log_audit_entry


@dataclass
class RepositoryConfig:
    session_factory: Any = SessionLocal


class MoralMatrixRepository:
    """Thin CRUD wrapper around SQLAlchemy models used by the MoralMatrix."""

    def __init__(self, config: RepositoryConfig | None = None) -> None:
        cfg = config or RepositoryConfig()
        self._session_factory = cfg.session_factory

    @contextmanager
    def _session(self) -> Iterable[Session]:
        session: Session = self._session_factory()
        try:
            yield session
        finally:
            session.close()

    # ------------------------------------------------------------------ #
    # Fetch helpers
    # ------------------------------------------------------------------ #
    def fetch_traces_for_messages(
        self, character_id: str, message_ids: Sequence[str]
    ) -> List[Dict[str, Any]]:
        if not message_ids:
            return []
        with self._session() as session:
            rows = (
                session.query(EmotionalTrace)
                .filter(
                    EmotionalTrace.character_id == character_id,
                    EmotionalTrace.message_id.in_(list(message_ids)),
                )
                .order_by(EmotionalTrace.created_at.desc())
                .all()
            )
            return [self._serialize_trace(row) for row in rows]

    def fetch_recent_traces(
        self, character_id: str, limit: int = 10
    ) -> List[Dict[str, Any]]:
        with self._session() as session:
            rows = (
                session.query(EmotionalTrace)
                .filter(EmotionalTrace.character_id == character_id)
                .order_by(EmotionalTrace.created_at.desc())
                .limit(limit)
                .all()
            )
            return [self._serialize_trace(row) for row in rows]

    def fetch_latest_snapshot(self, character_id: str) -> Optional[Dict[str, Any]]:
        with self._session() as session:
            row = (
                session.query(MoralStateSnapshot)
                .filter(MoralStateSnapshot.character_id == character_id)
                .order_by(MoralStateSnapshot.created_at.desc())
                .first()
            )
            return self._serialize_snapshot(row) if row else None

    def fetch_daily_summary(
        self, character_id: str, summary_date: date | None = None
    ) -> Optional[Dict[str, Any]]:
        target_date = summary_date or date.today()
        with self._session() as session:
            row = (
                session.query(DailyMoralSummary)
                .filter(
                    DailyMoralSummary.character_id == character_id,
                    DailyMoralSummary.date == target_date,
                )
                .order_by(DailyMoralSummary.updated_at.desc())
                .first()
            )
            return self._serialize_daily_summary(row) if row else None

    # ------------------------------------------------------------------ #
    # Mutations
    # ------------------------------------------------------------------ #
    def store_snapshot(
        self,
        character_id: str,
        message_id: Optional[str],
        payload: Dict[str, Any],
    ) -> Optional[str]:
        if not character_id:
            return None
        with self._session() as session:
            snapshot = MoralStateSnapshot(
                character_id=character_id,
                message_id=message_id,
                trust=float(payload.get("trust", 0.6)),
                stability=float(payload.get("stability", 0.6)),
                sociability=float(payload.get("sociability", 0.6)),
                resentment=float(payload.get("resentment", 0.05)),
                mood=payload.get("current_emotion", "neutral"),
                recommendations=json.dumps(
                    payload.get("recommendations", []), ensure_ascii=False
                ),
                hard_directives=json.dumps(
                    payload.get("hard_directives", []), ensure_ascii=False
                ),
                meta=json.dumps(payload.get("meta", {}), ensure_ascii=False),
            )
            session.add(snapshot)
            session.commit()
            session.refresh(snapshot)
            log_audit_entry(
                "moral_matrix_snapshot_saved",
                "[MoralMatrix] Snapshot persisted.",
                AuditStatus.SUCCESS,
                details={
                    "snapshot_id": snapshot.id,
                    "character_id": character_id,
                    "message_id": message_id,
                    "payload": payload,
                },
            )
            print(f"[MoralMatrix] Snapshot saved id: {snapshot.id}")
            return snapshot.id

    def store_emotional_trace(
        self,
        character_id: str,
        *,
        message_id: Optional[str],
        payload: Dict[str, Any],
    ) -> Optional[str]:
        if not character_id:
            return None
        with self._session() as session:
            trace = EmotionalTrace(
                character_id=character_id,
                message_id=message_id,
                trigger_role=payload.get("trigger_role", "assistant"),
                primary_emotion=payload.get("primary_emotion", "neutral"),
                secondary_emotion=payload.get("secondary_emotion"),
                intensity=float(payload.get("intensity", 0.0)),
                emotion_vector=json.dumps(
                    payload.get("emotion_vector", {}), ensure_ascii=False
                ),
                user_tone=payload.get("user_tone"),
                cause=payload.get("cause"),
                notes=payload.get("notes"),
            )
            session.add(trace)
            session.commit()
            session.refresh(trace)
            log_audit_entry(
                "moral_matrix_trace_saved",
                "[MoralMatrix] Emotional trace persisted.",
                AuditStatus.SUCCESS,
                details={
                    "trace_id": trace.id,
                    "character_id": character_id,
                    "message_id": message_id,
                    "primary": payload.get("primary_emotion"),
                    "intensity": payload.get("intensity"),
                },
            )
            print(
                f"[MoralMatrix] Trace saved id: {trace.id} ",
            )
            return trace.id

    # ------------------------------------------------------------------ #
    # Serialization helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _serialize_trace(row: EmotionalTrace) -> Dict[str, Any]:
        try:
            vector = json.loads(row.emotion_vector or "{}")
        except json.JSONDecodeError:
            vector = {}
        return {
            "id": row.id,
            "character_id": row.character_id,
            "message_id": row.message_id,
            "trigger_role": row.trigger_role,
            "primary_emotion": row.primary_emotion,
            "secondary_emotion": row.secondary_emotion,
            "intensity": float(row.intensity or 0.0),
            "emotion_vector": vector,
            "user_tone": row.user_tone,
            "cause": row.cause,
            "notes": row.notes,
            "created_at": (
                row.created_at.isoformat()
                if hasattr(row.created_at, "isoformat")
                else None
            ),
        }

    @staticmethod
    def _serialize_snapshot(row: MoralStateSnapshot) -> Dict[str, Any]:
        try:
            recommendations = json.loads(row.recommendations or "[]")
        except json.JSONDecodeError:
            recommendations = []
        try:
            hard_directives = json.loads(row.hard_directives or "[]")
        except json.JSONDecodeError:
            hard_directives = []
        try:
            meta = json.loads(row.meta or "{}")
        except json.JSONDecodeError:
            meta = {}
        return {
            "id": row.id,
            "trust": float(row.trust or 0.0),
            "stability": float(row.stability or 0.0),
            "sociability": float(row.sociability or 0.0),
            "resentment": float(row.resentment or 0.0),
            "mood": row.mood,
            "recommendations": recommendations,
            "hard_directives": hard_directives,
            "meta": meta,
            "created_at": (
                row.created_at.isoformat()
                if hasattr(row.created_at, "isoformat")
                else None
            ),
        }

    @staticmethod
    def _serialize_daily_summary(row: DailyMoralSummary) -> Dict[str, Any]:
        try:
            vector = json.loads(row.emotion_vector or "{}")
        except json.JSONDecodeError:
            vector = {}
        return {
            "id": row.id,
            "date": row.date.isoformat() if hasattr(row.date, "isoformat") else None,
            "dominant_emotion": row.dominant_emotion,
            "average_intensity": float(row.average_intensity or 0.0),
            "emotion_vector": vector,
            "trust": float(row.trust or 0.0),
            "stability": float(row.stability or 0.0),
            "sociability": float(row.sociability or 0.0),
            "resentment": float(row.resentment or 0.0),
            "summary": row.summary,
            "created_at": (
                row.created_at.isoformat()
                if hasattr(row.created_at, "isoformat")
                else None
            ),
        }
