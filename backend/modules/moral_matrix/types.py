"""Typed containers used by the MoralMatrix module."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class MoralMatrixMetrics:
    trust: float = 0.6
    stability: float = 0.6
    sociability: float = 0.6
    resentment: float = 0.05

    def clamp(self) -> None:
        self.trust = min(max(self.trust, 0.0), 1.0)
        self.stability = min(max(self.stability, 0.0), 1.0)
        self.sociability = min(max(self.sociability, 0.0), 1.0)
        self.resentment = min(max(self.resentment, 0.0), 1.0)

    def as_dict(self) -> Dict[str, float]:
        return {
            "trust": round(self.trust, 4),
            "stability": round(self.stability, 4),
            "sociability": round(self.sociability, 4),
            "resentment": round(self.resentment, 4),
        }


@dataclass
class EmotionalSnapshot:
    primary: str = "neutral"
    intensity: float = 0.0
    emotion_vector: Dict[str, float] = field(default_factory=dict)
    source: str = "analyzer"
    reasoning: Optional[str] = None


@dataclass
class MoralMatrixResult:
    current_emotion: str
    emotion_intensity: float
    relationship_status: str
    metrics: MoralMatrixMetrics = field(default_factory=MoralMatrixMetrics)
    emotion_vector: Dict[str, float] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)
    hard_directives: List[str] = field(default_factory=list)
    narrative: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "current_emotion": self.current_emotion,
            "emotion_intensity": round(self.emotion_intensity, 4),
            "relationship_status": self.relationship_status,
            "emotion_vector": self.emotion_vector,
            "metrics": self.metrics.as_dict(),
            "recommendations": list(self.recommendations),
            "hard_directives": list(self.hard_directives),
            "narrative": self.narrative,
            "meta": self.meta,
        }

