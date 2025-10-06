from typing import Dict, Any
from services.logger_service import log_audit_entry, AuditStatus

from constants.moral import (
    DEFAULT_EMOTIONAL_STATE,
    DEFAULT_RELATIONSHIP_SCORE,
    EMOTION_MAP,
    RELATIONSHIP_STATUSES,
    BEHAVIORAL_RECOMMENDATIONS,
    FALLBACK_RECOMMENDATION,
)


class MoralMatrix:
    """
    MoralMatrix evaluates emotional and relationship state,
    providing high-level signals for dialogue style and behavior.
    """

    def __init__(self):
        self.emotional_state = DEFAULT_EMOTIONAL_STATE.copy()
        self.relationship_score = DEFAULT_RELATIONSHIP_SCORE

    async def evaluate_state(self) -> Dict[str, Any]:
        """
        Evaluate current moral/emotional state.
        Picks dominant emotion and derives recommendations.

        Returns:
            Dict with:
                - current_emotion (str)
                - emotion_intensity (float)
                - relationship_status (str)
                - recommendations (list of str)
        """
        try:
            log_audit_entry(
                "moral_matrix_evaluation_start",
                "[MoralMatrix] Evaluating moral/emotional state.",
                AuditStatus.INFO,
            )

            dominant_emotion = max(self.emotional_state.items(), key=lambda x: x[1])

            result = {
                "current_emotion": self._emotion_to_text(dominant_emotion[0]),
                "emotion_intensity": dominant_emotion[1],
                "relationship_status": self._relationship_status(),
                "recommendations": self._get_behavioral_recommendations(
                    dominant_emotion[0]
                ),
            }

            log_audit_entry(
                "moral_matrix_evaluation_success",
                "[MoralMatrix] Evaluation completed successfully.",
                AuditStatus.SUCCESS,
                details=result,
            )

            return result

        except Exception as e:
            log_audit_entry(
                "moral_matrix_evaluation_error",
                f"[MoralMatrix] Error during evaluation: {e}",
                AuditStatus.ERROR,
                details={"error": str(e), "error_type": type(e).__name__},
            )
            return {
                "current_emotion": "neutral",
                "emotion_intensity": 0.0,
                "relationship_status": "unknown",
                "recommendations": FALLBACK_RECOMMENDATION,
            }

    def _emotion_to_text(self, emotion: str) -> str:
        """
        Convert internal emotion key to human-readable text.
        """
        return EMOTION_MAP.get(emotion, emotion)

    def _relationship_status(self) -> str:
        """
        Derive relationship status from score.
        """
        for threshold, status in RELATIONSHIP_STATUSES:
            if self.relationship_score > threshold:
                return status
        return RELATIONSHIP_STATUSES[-1][1]

    def _get_behavioral_recommendations(self, dominant_emotion: str) -> list[str]:
        """
        Get behavioral recommendations based on dominant emotion.
        """
        return BEHAVIORAL_RECOMMENDATIONS.get(dominant_emotion, FALLBACK_RECOMMENDATION)
