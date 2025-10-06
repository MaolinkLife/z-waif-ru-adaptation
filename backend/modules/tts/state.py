from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

from services.logger_service import log_audit_entry, AuditStatus


class VoiceStage(str, Enum):
    LISTENING = "listening"
    WAITING = "waiting"
    SPEAKING = "speaking"


@dataclass
class VoiceStateSnapshot:
    stage: VoiceStage
    changed_at: datetime
    reason: Optional[str]


class VoiceStateController:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._stage = VoiceStage.LISTENING
        self._changed_at = datetime.utcnow()
        self._reason: Optional[str] = None

    def _set_stage(self, stage: VoiceStage, reason: Optional[str]) -> None:
        with self._lock:
            if self._stage == stage and reason == self._reason:
                return
            self._stage = stage
            self._changed_at = datetime.utcnow()
            self._reason = reason

        log_audit_entry(
            "voice_state_transition",
            "[Voice] Stage updated",
            AuditStatus.INFO,
            details={"stage": stage.value, "reason": reason},
        )

    def enter_waiting(self, reason: Optional[str] = None) -> None:
        self._set_stage(VoiceStage.WAITING, reason)

    def enter_listening(self, reason: Optional[str] = None) -> None:
        self._set_stage(VoiceStage.LISTENING, reason)

    def enter_speaking(self, reason: Optional[str] = None) -> None:
        self._set_stage(VoiceStage.SPEAKING, reason)

    def stage(self) -> VoiceStage:
        with self._lock:
            return self._stage

    def snapshot(self) -> VoiceStateSnapshot:
        with self._lock:
            return VoiceStateSnapshot(self._stage, self._changed_at, self._reason)

    def is_listening(self) -> bool:
        return self.stage() == VoiceStage.LISTENING


voice_state = VoiceStateController()

__all__ = ["VoiceStage", "VoiceStateSnapshot", "voice_state", "VoiceStateController"]
