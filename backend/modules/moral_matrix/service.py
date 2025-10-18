"""High-level orchestration for the Moral Matrix module."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pprint import pformat
from typing import Any, Dict, List, Optional, Sequence, Tuple

from constants.moral import (
    DEFAULT_EMOTIONAL_STATE,
    DEFAULT_METRICS,
    EMOTION_SYNONYMS,
    NEGATIVE_EMOTIONS,
    POSITIVE_EMOTIONS,
    RELATIONSHIP_STATUSES,
    BEHAVIORAL_RECOMMENDATIONS,
    FALLBACK_RECOMMENDATION,
)
from modules.moral_matrix.repository import MoralMatrixRepository
from modules.moral_matrix.types import MoralMatrixMetrics, MoralMatrixResult
from modules.moral_matrix import heuristics
from modules.moral_matrix.providers import (
    HeuristicMoralProvider,
    OllamaMoralProvider,
    OpenRouterMoralProvider,
)
from modules.moral_matrix.providers.base import MoralMatrixProvider
from services import character_service
from services.config_service import get_config_value
from services.logger_service import AuditStatus, log_audit_entry


@dataclass
class ProviderRunResult:
    payload: Optional[Dict[str, Any]]
    provider: Optional[str]


class MoralMatrixProviderManager:
    """Controls the execution order of MoralMatrix providers."""

    def __init__(self) -> None:
        self._registry: Dict[str, MoralMatrixProvider] = {
            "heuristic": HeuristicMoralProvider(),
            "ollama": OllamaMoralProvider(),
            "openrouter": OpenRouterMoralProvider(),
        }

    async def run(self, payload: Dict[str, Any]) -> ProviderRunResult:
        errors: List[str] = []
        providers = self._resolve_providers()
        log_audit_entry(
            "moral_matrix_provider_chain",
            "[MoralMatrix] Provider execution order resolved.",
            AuditStatus.INFO,
            details={"order": [provider.name for provider in providers]},
        )
        print(
            "[MoralMatrix] Provider order:", [provider.name for provider in providers]
        )

        for provider in providers:
            if not provider.is_available():
                errors.append(f"{provider.name}_unavailable")
                continue
            result = await provider.run(payload)
            if result:
                return ProviderRunResult(payload=result, provider=provider.name)
        if errors:
            log_audit_entry(
                "moral_matrix.providers_unavailable",
                "[MoralMatrix] Providers unavailable.",
                AuditStatus.WARNING,
                details={"errors": errors},
            )
        return ProviderRunResult(payload=None, provider=None)

    def _resolve_providers(self) -> List[MoralMatrixProvider]:
        active = get_config_value("moral.active_provider", "heuristic")
        fallback = get_config_value("moral.fallback_order", []) or []

        order: List[str] = []
        if isinstance(active, str) and active:
            order.append(active)

        if isinstance(fallback, list):
            for name in fallback:
                if isinstance(name, str):
                    order.append(name)

        include_heuristic = False
        filtered_order: List[str] = []
        for name in order:
            if name == "heuristic":
                include_heuristic = True
                continue
            filtered_order.append(name)

        if include_heuristic or active == "heuristic" or not filtered_order:
            filtered_order.append("heuristic")

        order = filtered_order

        resolved: List[MoralMatrixProvider] = []
        for name in order:
            provider = self._registry.get(name)
            if provider and provider not in resolved:
                resolved.append(provider)

        for provider in self._registry.values():
            if provider not in resolved:
                resolved.append(provider)

        return resolved


class MoralMatrixModule:
    """Computes current emotional and moral directives for the system."""

    def __init__(self) -> None:
        self._repository = MoralMatrixRepository()
        self._provider_manager = MoralMatrixProviderManager()

    async def evaluate(
        self,
        analysis_result: Dict[str, Any],
        memory_context: Dict[str, Any],
        memory_meta: Dict[str, Any],
        *,
        message_meta: Optional[Dict[str, Any]] = None,
        user_message: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Evaluate current moral state and return structured guidance."""
        log_audit_entry(
            "moral_matrix_evaluate_start",
            "[MoralMatrix] Starting evaluation.",
            AuditStatus.INFO,
            details={
                "has_analysis": bool(analysis_result),
                "matches": len((memory_context or {}).get("matches", [])),
            },
        )

        if not bool(get_config_value("moral.enabled", True)):
            log_audit_entry(
                "moral_matrix_disabled",
                "[MoralMatrix] Module disabled in configuration.",
                AuditStatus.WARNING,
            )
            print("[MoralMatrix] Module disabled via config.")
            metrics = MoralMatrixMetrics(
                trust=DEFAULT_METRICS.get("trust", 0.6),
                stability=DEFAULT_METRICS.get("stability", 0.6),
                sociability=DEFAULT_METRICS.get("sociability", 0.6),
                resentment=DEFAULT_METRICS.get("resentment", 0.05),
            )
            return MoralMatrixResult(
                current_emotion="neutral",
                emotion_intensity=0.0,
                relationship_status=self._derive_relationship_status(metrics.trust),
                metrics=metrics,
                emotion_vector=dict(DEFAULT_EMOTIONAL_STATE),
                recommendations=FALLBACK_RECOMMENDATION,
                hard_directives=[],
                narrative="Moral Matrix disabled.",
                meta={"disabled": True},
            ).to_payload()

        character_id = self._resolve_character_id()

        history_ids = self._collect_history_ids(memory_context, message_meta)
        log_audit_entry(
            "moral_matrix_history_scope",
            "[MoralMatrix] History scope resolved.",
            AuditStatus.INFO,
            details={"history_ids": history_ids},
        )
        print("[MoralMatrix] History ids ->", history_ids)

        recent_traces = self._repository.fetch_recent_traces(character_id, limit=6)
        matched_traces = self._repository.fetch_traces_for_messages(
            character_id, history_ids
        )
        latest_snapshot = self._repository.fetch_latest_snapshot(character_id)
        daily_summary = self._repository.fetch_daily_summary(character_id, date.today())

        log_audit_entry(
            "moral_matrix_repository_payload",
            "[MoralMatrix] Repository data fetched.",
            AuditStatus.INFO,
            details={
                "recent_traces": len(recent_traces),
                "matched_traces": len(matched_traces),
                "latest_snapshot": bool(latest_snapshot),
                "daily_summary": bool(daily_summary),
            },
        )
        print("[MoralMatrix] Repo snapshot successful")

        metrics = self._bootstrap_metrics(latest_snapshot, daily_summary)
        emotion_vector = dict(DEFAULT_EMOTIONAL_STATE)

        self._apply_trace_context(emotion_vector, matched_traces, recent_traces)
        analyzer_snapshot = self._extract_analyzer_emotion(analysis_result)
        heuristic_snapshot = None
        if user_message and (
            not analyzer_snapshot.get("primary")
            or analyzer_snapshot["primary"] == "neutral"
        ):
            heuristic_snapshot = self._merge_heuristics(
                analyzer_snapshot,
                emotion_vector,
                user_message.get("content", ""),
            )

        current_emotion, emotion_intensity = self._blend_emotions(
            emotion_vector, analyzer_snapshot
        )
        self._apply_emotion_to_metrics(metrics, current_emotion, emotion_intensity)
        self._apply_memory_bias(metrics, matched_traces)
        self._apply_risk_bias(metrics, analysis_result)
        metrics.clamp()

        relationship_status = self._derive_relationship_status(metrics.trust)
        recommendations = self._derive_recommendations(current_emotion)
        hard_directives = self._derive_directives(metrics, analysis_result)

        provider_payload = {
            "current_emotion": current_emotion,
            "emotion_intensity": emotion_intensity,
            "metrics": metrics.as_dict(),
            "memory_traces": matched_traces,
            "recent_traces": recent_traces,
            "analysis_result": analysis_result,
            "relationship_status": relationship_status,
            "heuristics": heuristic_snapshot,
        }
        provider_result = await self._provider_manager.run(provider_payload)

        narrative: Optional[str] = None
        if provider_result.payload:
            narrative = provider_result.payload.get("summary")
            extra_directives = provider_result.payload.get("hard_directives") or []
            if extra_directives:
                hard_directives.extend(extra_directives)

        meta = {
            "history_ids": list(history_ids),
            "character_id": character_id,
            "provider": provider_result.provider,
            "previous_snapshot": (latest_snapshot or {}).get("id"),
            "daily_summary": (daily_summary or {}).get("id"),
            "matched_traces": len(matched_traces),
            "recent_traces": len(recent_traces),
            "memory_meta": {
                "matches_found": (memory_meta or {}).get("matches_found"),
                "short_term_record_id": (memory_meta or {}).get("short_term_record_id"),
            },
            "heuristics": heuristic_snapshot,
        }

        result = MoralMatrixResult(
            current_emotion=current_emotion,
            emotion_intensity=emotion_intensity,
            relationship_status=relationship_status,
            metrics=metrics,
            emotion_vector=emotion_vector,
            recommendations=recommendations,
            hard_directives=hard_directives,
            narrative=narrative,
            meta=meta,
        )

        self._persist_state(
            character_id,
            result,
            message_meta=message_meta,
            analyzer_snapshot=analyzer_snapshot,
            user_message=user_message,
        )

        payload = result.to_payload()
        log_audit_entry(
            "moral_matrix_evaluate_success",
            "[MoralMatrix] Evaluation complete.",
            AuditStatus.SUCCESS,
            details={
                "emotion": current_emotion,
                "intensity": round(emotion_intensity, 3),
                "relationship_status": relationship_status,
                "provider": provider_result.provider,
            },
        )
        return payload

    # ------------------------------------------------------------------ #
    # Bootstrap helpers
    # ------------------------------------------------------------------ #
    @staticmethod
    def _collect_history_ids(
        memory_context: Dict[str, Any], message_meta: Optional[Dict[str, Any]]
    ) -> List[str]:
        ids: List[str] = []
        matches = (memory_context or {}).get("matches", []) or []
        for item in matches:
            message_id = item.get("message_id")
            if message_id and message_id not in ids:
                ids.append(message_id)
        short_term_ids = (memory_context or {}).get("short_term_dialogue_ids")
        if isinstance(short_term_ids, str):
            try:
                import json

                decoded = json.loads(short_term_ids)
                if isinstance(decoded, list):
                    for mid in decoded:
                        if isinstance(mid, str) and mid not in ids:
                            ids.append(mid)
            except Exception:
                pass
        elif isinstance(short_term_ids, (list, tuple, set)):
            for mid in short_term_ids:
                if isinstance(mid, str) and mid not in ids:
                    ids.append(mid)

        current_id = (message_meta or {}).get("message_id")
        if current_id and current_id not in ids:
            ids.append(current_id)
        return ids

    def _bootstrap_metrics(
        self,
        latest_snapshot: Optional[Dict[str, Any]],
        daily_summary: Optional[Dict[str, Any]],
    ) -> MoralMatrixMetrics:
        metrics = MoralMatrixMetrics(
            trust=DEFAULT_METRICS.get("trust", 0.6),
            stability=DEFAULT_METRICS.get("stability", 0.6),
            sociability=DEFAULT_METRICS.get("sociability", 0.6),
            resentment=DEFAULT_METRICS.get("resentment", 0.05),
        )
        if latest_snapshot:
            metrics.trust = float(latest_snapshot.get("trust", metrics.trust))
            metrics.stability = float(
                latest_snapshot.get("stability", metrics.stability)
            )
            metrics.sociability = float(
                latest_snapshot.get("sociability", metrics.sociability)
            )
            metrics.resentment = float(
                latest_snapshot.get("resentment", metrics.resentment)
            )

        if daily_summary:
            metrics.trust = (metrics.trust + float(daily_summary.get("trust", 0.6))) / 2
            metrics.stability = (
                metrics.stability + float(daily_summary.get("stability", 0.6))
            ) / 2
            metrics.sociability = (
                metrics.sociability + float(daily_summary.get("sociability", 0.6))
            ) / 2
            metrics.resentment = (
                metrics.resentment + float(daily_summary.get("resentment", 0.05))
            ) / 2
        return metrics

    @staticmethod
    def _apply_trace_context(
        emotion_vector: Dict[str, float],
        matched_traces: Sequence[Dict[str, Any]],
        recent_traces: Sequence[Dict[str, Any]],
    ) -> None:
        for trace in (matched_traces or []) + (recent_traces or []):
            emotion = (trace.get("primary_emotion") or "neutral").lower()
            intensity = float(trace.get("intensity") or 0.0)
            if emotion not in emotion_vector:
                emotion_vector[emotion] = intensity
            else:
                emotion_vector[emotion] = max(emotion_vector[emotion], intensity)

    @staticmethod
    def _extract_analyzer_emotion(analysis_result: Dict[str, Any]) -> Dict[str, Any]:
        tone = (
            analysis_result.get("input_analysis", {}).get("emotional_tone", {})
            if isinstance(analysis_result, dict)
            else {}
        )
        primary = (tone.get("primary") or "neutral").lower()
        intensity = float(tone.get("intensity") or 0.3)
        secondary = [str(x).lower() for x in tone.get("secondary", []) if x]
        return {
            "primary": primary,
            "intensity": intensity,
            "secondary": secondary,
            "raw": tone,
        }

    def _merge_heuristics(
        self,
        analyzer_snapshot: Dict[str, Any],
        emotion_vector: Dict[str, float],
        message_text: str,
    ) -> Optional[Dict[str, Any]]:
        content = (message_text or "").strip()
        if not content:
            return None

        heuristic_analysis = heuristics.analyze_emotion(content)
        dominant = heuristic_analysis["meta"]["dominant_emotions"]
        if not dominant:
            return None

        normalized_primary = self._normalize_emotion(dominant[0])
        confidence = float(heuristic_analysis.get("confidence", 0.4))
        intensity = max(confidence, 0.35)
        emotion_vector[normalized_primary] = max(
            emotion_vector.get(normalized_primary, 0.0), intensity
        )

        if analyzer_snapshot.get("primary") in (None, "", "neutral"):
            analyzer_snapshot["primary"] = normalized_primary
            analyzer_snapshot["intensity"] = intensity

        analyzer_snapshot.setdefault("secondary", [])
        secondary = heuristic_analysis["meta"]["secondary_emotions"]
        for item in secondary:
            normalized_secondary = self._normalize_emotion(item)
            if normalized_secondary not in analyzer_snapshot["secondary"]:
                analyzer_snapshot["secondary"].append(normalized_secondary)
            emotion_vector[normalized_secondary] = max(
                emotion_vector.get(normalized_secondary, 0.0), 0.3
            )

        log_audit_entry(
            "moral_matrix_heuristic_merge",
            "[MoralMatrix] Applied heuristic emotion snapshot.",
            AuditStatus.INFO,
            details={
                "primary": normalized_primary,
                "intensity": intensity,
                "secondary": analyzer_snapshot.get("secondary", []),
            },
        )
        print(
            "[MoralMatrix] Heuristic snapshot merged ->",
            pformat(
                {
                    "primary": normalized_primary,
                    "confidence": confidence,
                    "secondary": secondary,
                }
            ),
        )

        return {
            "primary": normalized_primary,
            "intensity": intensity,
            "analysis": heuristic_analysis,
        }

    def _blend_emotions(
        self,
        emotion_vector: Dict[str, float],
        analyzer_snapshot: Dict[str, Any],
    ) -> Tuple[str, float]:
        primary = self._normalize_emotion(analyzer_snapshot.get("primary", "neutral"))
        intensity = min(max(analyzer_snapshot.get("intensity", 0.3), 0.0), 1.0)
        emotion_vector[primary] = max(emotion_vector.get(primary, 0.0), intensity)

        for secondary in analyzer_snapshot.get("secondary", []):
            normalized = self._normalize_emotion(secondary)
            emotion_vector[normalized] = max(emotion_vector.get(normalized, 0.0), 0.4)

        dominant_emotion = max(
            emotion_vector.items(),
            key=lambda item: item[1] if item[1] is not None else 0.0,
        )
        return dominant_emotion[0], float(dominant_emotion[1] or 0.0)

    def _apply_emotion_to_metrics(
        self, metrics: MoralMatrixMetrics, emotion: str, intensity: float
    ) -> None:
        if emotion in POSITIVE_EMOTIONS:
            metrics.trust += 0.1 * intensity
            metrics.sociability += 0.07 * intensity
            metrics.resentment = max(metrics.resentment - 0.05 * intensity, 0.0)
        elif emotion in NEGATIVE_EMOTIONS:
            metrics.stability = max(metrics.stability - 0.08 * intensity, 0.0)
            metrics.trust = max(metrics.trust - 0.06 * intensity, 0.0)
            metrics.resentment += 0.09 * intensity
        else:
            metrics.stability += 0.02 * (0.5 - abs(0.5 - intensity))

    @staticmethod
    def _apply_memory_bias(
        metrics: MoralMatrixMetrics, matched_traces: Sequence[Dict[str, Any]]
    ) -> None:
        if not matched_traces:
            return
        avg_intensity = sum(
            float(trace.get("intensity") or 0.0) for trace in matched_traces
        ) / max(len(matched_traces), 1)
        metrics.stability += 0.03 * avg_intensity

    @staticmethod
    def _apply_risk_bias(
        metrics: MoralMatrixMetrics, analysis_result: Dict[str, Any]
    ) -> None:
        risk_level = (
            analysis_result.get("risk_assessment", {}).get("risk_level", 0.0)
            if isinstance(analysis_result, dict)
            else 0.0
        )
        if risk_level >= 0.7:
            metrics.trust = max(metrics.trust - 0.2 * risk_level, 0.0)
            metrics.stability = max(metrics.stability - 0.15 * risk_level, 0.0)

    @staticmethod
    def _derive_relationship_status(score: float) -> str:
        for threshold, status in RELATIONSHIP_STATUSES:
            if score >= threshold:
                return status
        return RELATIONSHIP_STATUSES[-1][1] if RELATIONSHIP_STATUSES else "unknown"

    @staticmethod
    def _derive_recommendations(emotion: str) -> List[str]:
        return BEHAVIORAL_RECOMMENDATIONS.get(emotion, FALLBACK_RECOMMENDATION)

    @staticmethod
    def _derive_directives(
        metrics: MoralMatrixMetrics, analysis_result: Dict[str, Any]
    ) -> List[str]:
        directives: List[str] = []
        if metrics.resentment > 0.65:
            directives.append("system:lower_tone")
        if metrics.trust < 0.2:
            directives.append("system:avoid_sensitive_topics")
        risk_level = (
            analysis_result.get("risk_assessment", {}).get("risk_level", 0.0)
            if isinstance(analysis_result, dict)
            else 0.0
        )
        if risk_level >= 0.9:
            directives.append("system:defer_response")
        return directives

    def _persist_state(
        self,
        character_id: str,
        result: MoralMatrixResult,
        *,
        message_meta: Optional[Dict[str, Any]],
        analyzer_snapshot: Optional[Dict[str, Any]],
        user_message: Optional[Dict[str, Any]],
    ) -> None:
        message_id = (message_meta or {}).get("message_id")
        snapshot_payload = {
            **result.metrics.as_dict(),
            "current_emotion": result.current_emotion,
            "recommendations": result.recommendations,
            "hard_directives": result.hard_directives,
            "meta": {
                **result.meta,
                "narrative": result.narrative,
            },
        }
        self._repository.store_snapshot(character_id, message_id, snapshot_payload)

        trace_payload = {
            "trigger_role": (user_message or {}).get("role", "user"),
            "primary_emotion": result.current_emotion,
            "secondary_emotion": self._extract_secondary_emotion(analyzer_snapshot),
            "intensity": result.emotion_intensity,
            "emotion_vector": result.emotion_vector,
            "user_tone": (analyzer_snapshot or {}).get("primary"),
            "cause": (user_message or {}).get("content"),
        }
        self._repository.store_emotional_trace(
            character_id, message_id=message_id, payload=trace_payload
        )

    @staticmethod
    def _normalize_emotion(label: str) -> str:
        mapped = EMOTION_SYNONYMS.get(label.lower().strip())
        if mapped:
            return mapped
        return label.lower() if label else "neutral"

    @staticmethod
    def _extract_secondary_emotion(
        analyzer_snapshot: Optional[Dict[str, Any]],
    ) -> Optional[str]:
        if not analyzer_snapshot:
            return None
        secondary = analyzer_snapshot.get("secondary") or []
        if isinstance(secondary, (list, tuple)):
            for item in secondary:
                if item:
                    return str(item)
        return None

    @staticmethod
    def _resolve_character_id() -> str:
        char_name = get_config_value("system.char_name", "default_waifu")
        character = character_service.get_or_create_character(char_name)
        return character.id
