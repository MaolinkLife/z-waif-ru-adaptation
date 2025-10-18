# core/instructor.py
from typing import Dict, Any, List, Optional
from datetime import datetime

from core.prompt_loader import load_system_prompt
from services.config_service import get_config_value
from services.logger_service import log_audit_entry, AuditStatus
from services.localization_service import get_text
from constants.rules import SYSTEM_RULES
from constants.messages import DEFAULT_CONTEXT, NO_MEMORY, NO_KNOWLEDGE


class Instructor:
    """Assembles the final structured system prompt."""

    async def build_system_prompt(
        self,
        analysis: Dict[str, Any],
        decisions: Dict[str, bool],
        memory_context: Dict[str, Any],
        moral_state: Dict[str, Any],
        visual_context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Build the system prompt that will guide the model response."""
        try:
            print(
                get_text(
                    "instructor.print_start",
                    default="[Instructor] Старт сборки системного промпта.",
                )
            )
            log_audit_entry(
                "instructor_prompt_build_start",
                get_text(
                    "instructor.build_start",
                    default="[Instructor] Building system prompt.",
                ),
                AuditStatus.INFO,
                details={
                    "analysis_keys": list((analysis or {}).keys()),
                    "decisions": decisions,
                    "memory_meta": {
                        "has_key_facts": bool(
                            (memory_context or {}).get("key_facts")
                        ),
                        "matches": len((memory_context or {}).get("matches", [])),
                    },
                    "moral_state_keys": list((moral_state or {}).keys()),
                    "has_visual_context": bool(visual_context),
                },
                message_key="instructor.build_start",
            )

            base_prompt = load_system_prompt()
            print(
                get_text(
                    "instructor.print_base_loaded",
                    default="[Instructor] Загружен базовый промпт персонажа.",
                )
            )
            sections: List[str] = []
            section_map: Dict[str, Dict[str, Any]] = {}

            # [CORE] base persona prompt
            core_section = f"[CORE]\n{base_prompt}"
            sections.append(core_section)
            section_map["core"] = {
                "reason": "Base persona prompt",
                "content": base_prompt,
                "length": len(base_prompt),
            }

            # [CONTEXT] cognitive summary
            context_section = self._build_context_section(analysis)
            sections.append(context_section)
            section_map["context"] = {
                "reason": "Analyzer insights",
                "length": len(context_section),
                "summary": analysis.get("input_analysis", {}),
            }
            print(
                get_text(
                    "instructor.print_context_added",
                    default="[Instructor] Добавлен когнитивный контекст.",
                )
            )

            # [SYSTEM] environment data
            env_info = self._get_environment_info()
            if env_info:
                sections.append(f"[SYSTEM]\n{env_info}")
                section_map["system"] = {
                    "reason": "Environment information",
                    "content": env_info,
                }
                print(
                    get_text(
                        "instructor.print_system_added",
                        default="[Instructor] Добавлен системный контекст окружения.",
                    )
                )

            # [MEMORY] memory layer facts
            memory_section = self._build_memory_section(memory_context)
            sections.append(memory_section)
            section_map["memory"] = {
                "reason": "Memory facts",
                "length": len(memory_section),
                "facts_count": len(memory_context.get("key_facts") or []),
            }
            print(
                get_text(
                    "instructor.print_memory_added",
                    default="[Instructor] Добавлен блок памяти.",
                )
            )

            # [KNOWLEDGE] lore context
            knowledge_section = self._build_knowledge_section(memory_context)
            sections.append(knowledge_section)
            section_map["knowledge"] = {
                "reason": "Lore knowledge",
                "length": len(knowledge_section),
                "has_lore_matches": bool(
                    (memory_context.get("lore_matches") or [])
                ),
            }
            print(
                get_text(
                    "instructor.print_knowledge_added",
                    default="[Instructor] Добавлен блок знаний.",
                )
            )

            # [INSTRUCTION] persona tweaks (currently disabled, reserved)
            persona_section = self._build_persona_section(analysis)
            if persona_section:
                sections.append(persona_section)
                section_map["persona"] = {
                    "reason": "Persona adjustments",
                    "length": len(persona_section),
                }

            # [EMOTION] moral state summary
            current_emotion = moral_state.get("current_emotion", "neutral")
            sections.append(f"[EMOTION]\nCurrent emotional state: {current_emotion}")
            section_map["emotion"] = {
                "reason": "Moral matrix emotion summary",
                "value": current_emotion,
            }
            print(
                get_text(
                    "instructor.print_emotion_added",
                    default="[Instructor] Добавлен эмоциональный контекст.",
                )
            )

            # [RULES] hard constraints
            sections.append(f"[RULES]\n" + "\n".join(SYSTEM_RULES))
            section_map["rules"] = {
                "reason": "Hard system rules",
                "rules_count": len(SYSTEM_RULES),
            }
            print("[Instructor] Добавлены системные правила.")

            # [DECISIONS] active routing decisions
            active_decisions = [key for key, value in decisions.items() if value]
            if active_decisions:
                sections.append(
                    f"[DECISIONS]\nActive modes: {', '.join(active_decisions)}"
                )
                section_map["decisions"] = {
                    "reason": "Active decision flags",
                    "active": active_decisions,
                }
                print("[Instructor] Добавлены активные решения.")

            # [VISUAL] visual context supplied by decision layer
            visual_section = self._render_visual_context(visual_context)
            if visual_section:
                sections.append(f"[CONTEXT:VISION]\n{visual_section}")
                section_map["vision"] = {
                    "reason": "Visual context",
                    "items": len(
                        (visual_context or {})
                        .get("attachments", {})
                        .get("items", [])
                    ),
                    "has_screen": bool((visual_context or {}).get("screen")),
                }
                print("[Instructor] Добавлен визуальный контекст.")
                attachments_count = len(
                    (visual_context or {}).get("attachments", {}).get("items", [])
                )
                log_audit_entry(
                    "instructor_visual_context_added",
                    "[Instructor] Visual context appended to system prompt.",
                    AuditStatus.SUCCESS,
                    details={
                        "attachments": attachments_count,
                        "has_screen": bool((visual_context or {}).get("screen")),
                    },
                )
            else:
                log_audit_entry(
                    "instructor_visual_context_skipped",
                    "[Instructor] No visual context appended to system prompt.",
                    AuditStatus.INFO,
                    details={
                        "provided": bool(visual_context),
                        "attachments": (
                            len(
                                (visual_context or {})
                                .get("attachments", {})
                                .get("items", [])
                            )
                            if visual_context
                            else 0
                        ),
                        "has_screen": bool((visual_context or {}).get("screen")),
                    },
                )

            final_prompt = "\n\n".join(sections)
            print(
                get_text(
                    "instructor.print_complete",
                    default="[Instructor] Системный промпт собран.",
                )
            )

            log_audit_entry(
                "instructor_prompt_build_success",
                get_text(
                    "instructor.build_success",
                    default="[Instructor] System prompt successfully built.",
                ),
                AuditStatus.SUCCESS,
                details={
                    "sections_count": len(sections),
                    "has_visual_context": bool(visual_section),
                    "prompt_sections": section_map,
                    "final_prompt": final_prompt,
                },
                message_key="instructor.build_success",
            )

            return final_prompt

        except Exception as exc:
            error_text = str(exc)
            log_audit_entry(
                "instructor_prompt_build_error",
                get_text(
                    "instructor.build_error",
                    params={"error": error_text},
                    default="[Instructor] Error while building system prompt: {error}",
                ),
                AuditStatus.ERROR,
                details={"error": error_text, "error_type": type(exc).__name__},
                message_key="instructor.build_error",
                message_args={"error": error_text},
            )
            return "[CORE]\nSystem prompt unavailable due to error."

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------
    def _build_context_section(self, analysis: Dict[str, Any]) -> str:
        context_parts: List[str] = []

        themes = analysis.get("input_analysis", {}).get("dominant_themes", [])
        if themes:
            context_parts.append(f"Themes: {', '.join(themes)}")

        intent = (
            analysis.get("input_analysis", {})
            .get("intent_analysis", {})
            .get("primary_intent", "")
        )
        if intent:
            context_parts.append(f"Intent: {intent}")

        emotional_tone = (
            analysis.get("input_analysis", {})
            .get("emotional_tone", {})
            .get("primary", "")
        )
        if emotional_tone:
            context_parts.append(f"Emotional tone: {emotional_tone}")

        if context_parts:
            return f"[CONTEXT]\n{'; '.join(context_parts)}"
        return f"[CONTEXT]\n{DEFAULT_CONTEXT}"

    def _build_memory_section(self, memory_context: Dict[str, Any]) -> str:
        key_facts = memory_context.get("key_facts")
        if key_facts:
            return f"[MEMORY]\n{'; '.join(key_facts)}"
        return f"[MEMORY]\n{NO_MEMORY}"

    def _build_knowledge_section(self, memory_context: Dict[str, Any]) -> str:
        lore_matches = memory_context.get("lore_matches")
        if lore_matches:
            return f"[KNOWLEDGE]\n" + "\n---\n".join(lore_matches)
        return f"[KNOWLEDGE]\n{NO_KNOWLEDGE}"

    def _build_persona_section(self, analysis: Dict[str, Any]) -> str:
        persona_constraints = (
            analysis.get("response_guidance", {})
            .get("generation_parameters", {})
            .get("persona_constraints", [])
        )
        # Persona adjustments are intentionally disabled to preserve the base character profile.
        if persona_constraints:  # pragma: no cover - informative branch only
            return ""
        return ""

    def _render_visual_context(self, visual_context: Optional[Dict[str, Any]]) -> str:
        if not visual_context:
            return ""

        lines: List[str] = []

        attachments = (visual_context.get("attachments") or {}).get("items", [])
        for idx, item in enumerate(attachments, start=1):
            description = (item.get("description") or "").strip()
            if not description:
                continue
            label = (
                item.get("label")
                or item.get("name")
                or item.get("filename")
                or f"Attachment {idx}"
            )
            lines.append(f"{label}: {description}")

        screen_info = visual_context.get("screen") or {}
        screen_description = (screen_info.get("description") or "").strip()
        if screen_description:
            timestamp = screen_info.get("captured_at")
            prefix = "Screen snapshot"
            if timestamp:
                prefix = f"{prefix} ({timestamp})"
            lines.append(f"{prefix}: {screen_description}")

        return "\n".join(lines)

    def _get_environment_info(self) -> str:
        now = datetime.now()
        date_str = now.strftime("%d %B %Y")
        time_str = now.strftime("%H:%M:%S")

        from services.config_service import get_config_value

        location = get_config_value("location", "unknown")
        coordinates = get_config_value("coordinates", None)

        parts = [
            f"Date: {date_str}",
            f"Time: {time_str}",
        ]

        if location and location != "unknown":
            parts.append(f"Location: {location}")

        if coordinates:
            parts.append(f"Coordinates: {coordinates}")

        return "\n".join(parts)

    def _build_attachment_summary(
        self, media_list: Optional[List[Dict[str, Any]]]
    ) -> str:
        if not media_list:
            return ""

        image_descriptions: List[str] = []
        image_index = 0
        for media in media_list:
            if (media.get("category") or "").lower() != "image":
                continue
            image_index += 1
            summary = (media.get("description") or "").strip()
            if summary:
                label = f"Image {image_index}" if image_index > 1 else "Image"
                image_descriptions.append(f"{label}: {summary}")

        if not image_descriptions:
            return ""

        lines = "\n".join(image_descriptions)
        return "User provided image attachments:\n" + lines

    async def format_for_api(
        self, system_prompt: str, user_message: Dict[str, Any]
    ) -> list:
        print(
            get_text(
                "instructor.print_format_start",
                default="[Instructor] Форматируем историю для генератора.",
            )
        )
        log_audit_entry(
            "instructor_format_for_api",
            get_text(
                "instructor.format_start",
                default="[Instructor] Formatting message history for API.",
            ),
            AuditStatus.INFO,
            details={
                "message_id": user_message.get("id"),
                "history_length": len(user_message.get("history", [])),
                "system_prompt_preview": system_prompt[:500],
                "history_limit_raw": get_config_value("rag.history_limit", 10),
            },
            message_key="instructor.format_start",
        )

        history = user_message.get("history", [])
        history_limit_raw = get_config_value("rag.history_limit", 10)
        try:
            history_limit = int(history_limit_raw)
        except (TypeError, ValueError):
            history_limit = 10
        history_limit = max(history_limit, 0)
        recent_history = history[-history_limit:] if history_limit else []

        messages = [{"role": "system", "content": system_prompt}]

        for msg in recent_history:
            if msg.get("role") == "system":
                continue
            enriched_msg = {
                "role": msg.get("role"),
                "content": msg.get("content"),
                "id": msg.get("id"),
            }
            if "media" in msg:
                enriched_msg["media"] = msg.get("media")
            messages.append(enriched_msg)

        enriched_user = {
            "role": "user",
            "content": user_message.get("content", ""),
            "id": user_message.get("id"),
        }
        if "media" in user_message:
            enriched_user["media"] = user_message.get("media")
        messages.append(enriched_user)

        log_audit_entry(
            "instructor_format_for_api_result",
            get_text(
                "instructor.format_success",
                default="[Instructor] History formatted for generator.",
            ),
            AuditStatus.SUCCESS,
            details={
                "total_messages": len(messages),
                "user_message_id": user_message.get("id"),
                "message_roles": [msg.get("role") for msg in messages],
                "history_messages_used": len(recent_history),
                "history_limit": history_limit,
            },
            message_key="instructor.format_success",
        )
        print(
            get_text(
                "instructor.print_format_complete",
                default="[Instructor] Формирование истории завершено.",
            )
        )

        return messages
