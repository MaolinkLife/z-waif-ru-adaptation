"""Heuristic moral provider used as default fallback."""

from __future__ import annotations

from typing import Any, Dict, Optional

from .base import MoralMatrixProvider


class HeuristicMoralProvider(MoralMatrixProvider):
    """Generates a lightweight narrative without calling external services."""

    name = "heuristic"

    async def run(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        metrics = payload.get("metrics") or {}
        emotion = payload.get("current_emotion", "neutral")
        intensity = payload.get("emotion_intensity", 0.0)

        trust = metrics.get("trust", 0.5)
        resentment = metrics.get("resentment", 0.0)

        tone_parts = [f"emotion: {emotion} ({intensity:.2f})"]
        tone_parts.append(f"trust={trust:.2f}")
        tone_parts.append(f"resentment={resentment:.2f}")

        narrative = " | ".join(tone_parts)

        hard_directives: list[str] = []
        if resentment > 0.7:
            hard_directives.append("system:delay_response")
        if trust < 0.2:
            hard_directives.append("system:withhold_private_topics")

        return {
            "summary": narrative,
            "hard_directives": hard_directives,
        }

