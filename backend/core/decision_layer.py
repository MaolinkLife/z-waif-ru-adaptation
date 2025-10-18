import asyncio
import hashlib
from typing import Dict, Any, List, Optional, Tuple
from pprint import pprint

from modules.moral_matrix import MoralMatrixModule
from core.instructor import Instructor
from core.visual_module import VisualModule
from modules.analyzer.service import AnalyzerModule
from modules.tts.service import speak_line
from modules.memory import MemoryModule

from constants.indicators import (
    VISION_INDICATORS,
    VISION_KEYWORDS,
    DEEP_MEMORY_THEMES,
    SEARCH_THEMES,
    SUPPORT_EMOTIONS,
    CREATIVE_THEMES,
)

from services.config_service import get_config_value
from services.logger_service import log_audit_entry, AuditStatus


class DecisionLayer:
    """
    Decision layer orchestrates message processing pipeline:
    - Runs cognitive analysis
    - Makes routing decisions
    - Collects memory/lore context
    - Evaluates moral state
    - Builds final system prompt
    """

    def __init__(self):
        self.memory_module = MemoryModule()
        self.moral_matrix = MoralMatrixModule()
        self.instructor = Instructor()
        self.analyzer = AnalyzerModule()
        self._visual_module: Optional[VisualModule] = None
        self._visual_module_failed: bool = False
        # Логирование инициализации
        print("[DecisionLayer] Модуль DecisionLayer инициализирован.")
        log_audit_entry(
            "decision_layer_init",
            "[DecisionLayer] Модуль DecisionLayer инициализирован.",
            AuditStatus.INFO,
        )

        print("[DecisionLayer] Подключаем общий TTS сервис.")
        log_audit_entry(
            "decision_layer_tts_service_linked",
            "[DecisionLayer] DecisionLayer использует общий TTS сервис.",
            AuditStatus.INFO,
        )

    # --------------------------------------------------------------------- #
    #                     PUBLIC API
    # --------------------------------------------------------------------- #
    async def process_message(
        self, user_message: Dict[str, Any], websocket
    ) -> Dict[str, Any]:
        """
        Main entry point for message processing pipeline.
        """
        safe_user_message, raw_media_payload = self._prepare_user_payload(
            user_message
        )

        print("[DecisionLayer] Запуск обработки сообщения.")
        log_audit_entry(
            "decision_layer_start",
            "[DecisionLayer] Начало обработки сообщения.",
            AuditStatus.INFO,
            details={
                "message_id": safe_user_message.get("id"),
                "media_count": len(raw_media_payload),
                "has_media": bool(raw_media_payload),
                "content_length": len(safe_user_message.get("content") or ""),
            },
        )

        # --------------------------------------------------------------- #
        # 1️⃣  Cognitive analysis
        # --------------------------------------------------------------- #
        print("[DecisionLayer] Запрос анализа данных анализатором.")
        log_audit_entry(
            "decision_layer_analyzer_request",
            "[DecisionLayer] Запрос на анализ данных.",
            AuditStatus.INFO,
            details={
                "message_id": safe_user_message.get("id"),
                "media": safe_user_message.get("media"),
            },
        )
        analysis_payload = await self.analyzer.analyze(safe_user_message)
        print("[DecisionLayer] Анализ завершен.")
        log_audit_entry(
            "decision_layer_analyzer_response",
            "[DecisionLayer] Анализ завершен.",
            AuditStatus.INFO,
            details={"analysis_payload": analysis_payload},
        )
        analysis_result = analysis_payload.get("metadata", {})

        # --------------------------------------------------------------- #
        # 2️⃣  Decision‑making
        # --------------------------------------------------------------- #
        print("[DecisionLayer] Принятие решений на основе анализа.")
        log_audit_entry(
            "decision_layer_decision_request",
            "[DecisionLayer] Принятие решений на основе анализа.",
            AuditStatus.INFO,
            details={"analysis_result": analysis_result},
        )
        decisions = self._make_decisions(analysis_result)
        print("[DecisionLayer] Решения приняты.")
        log_audit_entry(
            "decision_layer_decisions_made",
            "[DecisionLayer] Решения приняты.",
            AuditStatus.INFO,
            details={"decisions": decisions},
        )

        # --------------------------------------------------------------- #
        # 3️⃣  Gather context from memory and lore
        # --------------------------------------------------------------- #
        print("[DecisionLayer] Сбор контекста из памяти и легенд.")
        log_audit_entry(
            "decision_layer_memory_context_request",
            "[DecisionLayer] Запрос на сбор контекста из памяти.",
            AuditStatus.INFO,
            details={"user_message": safe_user_message},
        )
        memory_result = await self.memory_module.collect_context(
            safe_user_message.get("content", ""), safe_user_message
        )
        print("[DecisionLayer] Контекст из памяти собран.")
        log_audit_entry(
            "decision_layer_memory_context_collected",
            "[DecisionLayer] Контекст из памяти собран.",
            AuditStatus.INFO,
            details={
                "memory_result": {
                    "context": memory_result.context,
                    "meta": memory_result.meta,
                }
            },
        )
        memory_context = memory_result.context
        memory_meta = memory_result.meta
        lore_context = {
            "lore_matches": memory_context.get("lore_matches", []),
            "lore_block": memory_context.get("lore_block"),
            "count": memory_context.get("count"),
        }

        history_preview = memory_context.get("recent_history") or []
        sanitized_history = self._sanitize_history_entries(history_preview)
        safe_user_message["history"] = sanitized_history
        if sanitized_history:
            history_meta = memory_meta.get("history_preview", {}) if isinstance(memory_meta, dict) else {}
            history_limit_config = history_meta.get("limit", len(history_preview))
            log_audit_entry(
                "decision_layer_history_attached",
                "[DecisionLayer] История сообщений прикреплена к пользовательскому запросу.",
                AuditStatus.INFO,
                details={
                    "messages_attached": len(sanitized_history),
                    "history_limit": history_limit_config,
                },
            )

        # --------------------------------------------------------------- #
        # 5️⃣  Evaluate moral state
        # --------------------------------------------------------------- #
        print("[DecisionLayer] Оценка морального состояния.")
        log_audit_entry(
            "decision_layer_moral_state_request",
            "[DecisionLayer] Запрос на оценку морального состояния.",
            AuditStatus.INFO,
        )
        message_meta = analysis_payload.get("message_meta", {})
        moral_state = await self.moral_matrix.evaluate(
            analysis_result,
            memory_context,
            memory_meta,
            message_meta=message_meta,
            user_message=safe_user_message,
        )
        print("[DecisionLayer] Моральное состояние оценено.")
        log_audit_entry(
            "decision_layer_moral_state_evaluated",
            "[DecisionLayer] Моральное состояние оценено.",
            AuditStatus.INFO,
            details={"moral_state": moral_state},
        )

        # --------------------------------------------------------------- #
        # 5️⃣  Gather visual context when available
        # --------------------------------------------------------------- #
        print("[DecisionLayer] Сбор визуального контекста.")
        log_audit_entry(
            "decision_layer_visual_context_request",
            "[DecisionLayer] Запрос на сбор визуального контекста.",
            AuditStatus.INFO,
            details={
                "media": safe_user_message.get("media"),
                "decisions": decisions,
            },
        )
        visual_context = await self._collect_visual_context(
            raw_media_payload, decisions
        )
        if raw_media_payload:
            safe_user_message["media"] = self._sanitize_media_list(raw_media_payload)
        print("[DecisionLayer] Визуальный контекст собран.")
        log_audit_entry(
            "decision_layer_visual_context_collected",
            "[DecisionLayer] Визуальный контекст собран.",
            AuditStatus.INFO,
            details={"visual_context": visual_context},
        )

        # --------------------------------------------------------------- #
        # 6️⃣  Build final system prompt
        # --------------------------------------------------------------- #
        print("[DecisionLayer] Формирование финального системного запроса.")
        log_audit_entry(
            "decision_layer_system_prompt_request",
            "[DecisionLayer] Запрос на формирование системного запроса.",
            AuditStatus.INFO,
            details={
                "analysis_result": analysis_result,
                "decisions": decisions,
                "memory_context": memory_context,
                "moral_state": moral_state,
                "visual_context": visual_context,
            },
        )
        system_prompt = await self.instructor.build_system_prompt(
            analysis_result,
            decisions,
            memory_context,
            moral_state,
            visual_context=visual_context,
        )
        prompt_hash = hashlib.sha256(system_prompt.encode()).hexdigest()[:12]
        print("[DecisionLayer] Финальный системный запрос сформирован.")
        log_audit_entry(
            "decision_layer_system_prompt_built",
            "[DecisionLayer] Финальный системный запрос сформирован.",
            AuditStatus.INFO,
            details={
                "prompt_length": len(system_prompt),
                "prompt_hash": prompt_hash,
            },
        )

        # --------------------------------------------------------------- #
        # 7️⃣  Final audit log
        # --------------------------------------------------------------- #
        print("[DecisionLayer] Обработка сообщения завершена успешно.")
        log_audit_entry(
            "decision_layer_success",
            "[DecisionLayer] Сообщение обработано успешно.",
            AuditStatus.SUCCESS,
            details={
                "decisions": decisions,
                "visual_context": {
                    "attachments": len(
                        (visual_context.get("attachments", {}) or {}).get("items", [])
                    ),
                    "has_screen": bool(visual_context.get("screen")),
                },
                "memory_meta": memory_meta,
                "moral_state": moral_state,
                "system_prompt_hash": prompt_hash,
            },
        )

        return {
            "system_prompt": system_prompt,
            "user_message": safe_user_message,
            "raw_media": raw_media_payload,
            "decisions": decisions,
            "analysis": analysis_result,
            "analysis_details": analysis_payload,
            "visual_context": visual_context,
            "memory_context": memory_context,
            "memory_meta": memory_meta,
        }

    def handle_response(self, text: str) -> None:
        if not text:
            return
        print("[DecisionLayer] Обработка ответа для озвучки.")
        log_audit_entry(
            "decision_layer_tts_request",
            "[DecisionLayer] Запрос на озвучку текста.",
            AuditStatus.INFO,
            details={"text": text},
        )
        if not get_config_value("voice.enabled", False):
            print("[DecisionLayer] Озвучка отключена в конфигурации.")
            log_audit_entry(
                "decision_layer_tts_disabled",
                "[DecisionLayer] Озвучка отключена в конфигурации.",
                AuditStatus.INFO,
            )
            return

        try:
            print("[DecisionLayer] Передаём текст в общий TTS сервис.")
            success = speak_line(text)
            log_audit_entry(
                "decision_layer_tts_success",
                "[DecisionLayer] Текст успешно передан в очередь сервису.",
                AuditStatus.INFO if success else AuditStatus.WARNING,
                details={
                    "queued": success,
                    "text_length": len(text),
                },
            )
            print(
                "[DecisionLayer] Текст отправлен в очередь для озвучки."
                if success
                else "[DecisionLayer] Общий TTS сервис отклонил запрос."
            )
        except Exception as exc:
            print(f"[DecisionLayer] Ошибка при озвучке: {exc}")
            log_audit_entry(
                "decision_layer_tts_error",
                "[DecisionLayer] Ошибка при озвучке текста.",
                AuditStatus.ERROR,
                details={"error": str(exc)},
            )

    # --------------------------------------------------------------------- #
    #                     PRIVATE HELPERS
    # --------------------------------------------------------------------- #
    @classmethod
    def _prepare_user_payload(
        cls, user_message: Dict[str, Any]
    ) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
        """
        Return a sanitized representation of the incoming message alongside
        a copy of raw media payload that may still contain binary/base64 data.
        """
        if not isinstance(user_message, dict):
            return {}, []

        media_payload: List[Dict[str, Any]] = []
        for item in user_message.get("media") or []:
            if isinstance(item, dict):
                media_payload.append(dict(item))

        message_copy: Dict[str, Any] = {k: v for k, v in user_message.items()}
        message_copy["media"] = media_payload

        history = message_copy.get("history")
        if isinstance(history, list):
            history_copy: List[Dict[str, Any]] = []
            for entry in history:
                if not isinstance(entry, dict):
                    history_copy.append(entry)
                    continue
                entry_copy = {k: v for k, v in entry.items()}
                entry_media = entry_copy.get("media")
                if isinstance(entry_media, list):
                    entry_copy["media"] = [
                        dict(media_item)
                        for media_item in entry_media
                        if isinstance(media_item, dict)
                    ]
                history_copy.append(entry_copy)
            message_copy["history"] = history_copy

        safe_message = cls._sanitize_message_payload(message_copy)
        return safe_message, media_payload

    @classmethod
    def _sanitize_message_payload(cls, message: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(message, dict):
            return {}

        sanitized: Dict[str, Any] = {
            k: v for k, v in message.items() if k not in {"media", "history"}
        }
        sanitized["media"] = cls._sanitize_media_list(message.get("media") or [])

        history = message.get("history")
        if isinstance(history, list):
            sanitized_history: List[Dict[str, Any]] = []
            for entry in history:
                if isinstance(entry, dict):
                    entry_sanitized = {
                        k: v for k, v in entry.items() if k not in {"media"}
                    }
                    entry_sanitized["media"] = cls._sanitize_media_list(
                        entry.get("media") or []
                    )
                    sanitized_history.append(entry_sanitized)
                else:
                    sanitized_history.append(entry)
            sanitized["history"] = sanitized_history

        return sanitized

    @classmethod
    def _sanitize_media_list(
        cls, media_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        sanitized: List[Dict[str, Any]] = []
        for item in media_list or []:
            cleaned = cls._sanitize_media_item(item)
            if cleaned:
                sanitized.append(cleaned)
        return sanitized

    @classmethod
    def _sanitize_history_entries(
        cls, history: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        sanitized: List[Dict[str, Any]] = []
        for entry in history or []:
            if not isinstance(entry, dict):
                continue
            cleaned: Dict[str, Any] = {
                "role": entry.get("role"),
                "content": entry.get("content"),
            }
            if entry.get("id"):
                cleaned["id"] = entry.get("id")
            if entry.get("timestamp"):
                cleaned["timestamp"] = entry.get("timestamp")
            media_items = entry.get("media")
            if isinstance(media_items, list) and media_items:
                cleaned_media = cls._sanitize_media_list(media_items)
                if cleaned_media:
                    cleaned["media"] = cleaned_media
            sanitized.append(cleaned)
        return sanitized

    @staticmethod
    def _sanitize_media_item(media: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(media, dict):
            return {}

        sanitized: Dict[str, Any] = {}

        def _assign(key: str, value: Any) -> None:
            if value is None:
                return
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    return
            sanitized[key] = value

        _assign("id", media.get("id"))
        _assign("name", media.get("name") or media.get("filename"))
        _assign(
            "mimeType",
            media.get("mimeType")
            or media.get("mime_type")
            or media.get("contentType")
            or media.get("type"),
        )
        _assign("category", media.get("category") or media.get("mediaType"))
        size = media.get("size")
        if size is not None:
            sanitized["size"] = size
        duration = media.get("duration")
        if duration is not None:
            sanitized["duration"] = duration
        for key in ("width", "height"):
            if media.get(key) is not None:
                sanitized[key] = media.get(key)
        _assign("description", media.get("description") or media.get("summary"))
        _assign("url", media.get("url"))
        _assign("thumbnailUrl", media.get("thumbnailUrl"))
        return sanitized

    def _make_decisions(self, analysis: Dict) -> Dict[str, bool]:
        """Derive high-level routing decisions based on analysis results."""
        themes = analysis.get("input_analysis", {}).get("dominant_themes", [])
        decisions = {
            "needs_vision": self._should_use_vision(analysis),
            "needs_deep_memory": self._should_use_deep_memory(themes),
            "needs_web_search": self._should_use_web_search(themes),
            "needs_emotional_support": self._should_provide_emotional_support(analysis),
            "needs_creative_mode": self._should_use_creative_mode(themes),
        }
        print("[DecisionLayer] Решения приняты: ", decisions)
        log_audit_entry(
            "decision_layer_decisions_derived",
            "[DecisionLayer] Решения приняты.",
            AuditStatus.INFO,
            details={"decisions": decisions},
        )
        return decisions

    def _should_use_vision(self, analysis: Dict) -> bool:
        """
        Determine if visual module should be engaged.
        """
        themes = analysis.get("input_analysis", {}).get("dominant_themes", [])
        category = analysis.get("input_analysis", {}).get("content_category", "")
        primary_intent = (
            analysis.get("input_analysis", {})
            .get("intent_analysis", {})
            .get("primary_intent", "")
        )

        has_vision_theme = any(theme in themes for theme in VISION_INDICATORS["themes"])
        has_vision_intent = primary_intent in VISION_INDICATORS["intents"]
        has_vision_category = category in VISION_INDICATORS["categories"]

        original_message = (
            analysis.get("input_analysis", {}).get("original_message", "").lower()
        )
        has_keyword = any(keyword in original_message for keyword in VISION_KEYWORDS)

        result = (
            has_vision_theme or has_vision_intent or has_vision_category or has_keyword
        )
        print(f"[DecisionLayer] Необходимость использования зрения: {result}")
        log_audit_entry(
            "decision_layer_vision_decision",
            "[DecisionLayer] Решение о необходимости использования зрения.",
            AuditStatus.INFO,
            details={"result": result},
        )
        return result

    def _should_use_deep_memory(self, themes: List[str]) -> bool:
        """Check if deep memory module should be used."""
        result = any(theme in DEEP_MEMORY_THEMES for theme in themes)
        print(f"[DecisionLayer] Необходимость использования глубокой памяти: {result}")
        log_audit_entry(
            "decision_layer_deep_memory_decision",
            "[DecisionLayer] Решение о необходимости использования глубокой памяти.",
            AuditStatus.INFO,
            details={"result": result},
        )
        return result

    def _should_use_web_search(self, themes: List[str]) -> bool:
        """Check if web search should be used."""
        result = any(theme in SEARCH_THEMES for theme in themes)
        print(
            f"[DecisionLayer] Необходимость использования поиска в интернете: {result}"
        )
        log_audit_entry(
            "decision_layer_web_search_decision",
            "[DecisionLayer] Решение о необходимости использования поиска в интернете.",
            AuditStatus.INFO,
            details={"result": result},
        )
        return result

    def _should_provide_emotional_support(self, analysis: Dict) -> bool:
        """Check if emotional support is required."""
        primary_emotion = (
            analysis.get("input_analysis", {})
            .get("emotional_tone", {})
            .get("primary", "")
        )
        result = any(emotion in primary_emotion.lower() for emotion in SUPPORT_EMOTIONS)
        print(f"[DecisionLayer] Необходимость эмоциональной поддержки: {result}")
        log_audit_entry(
            "decision_layer_emotional_support_decision",
            "[DecisionLayer] Решение о необходимости эмоциональной поддержки.",
            AuditStatus.INFO,
            details={"result": result},
        )
        return result

    def _should_use_creative_mode(self, themes: List[str]) -> bool:
        """Check if creative mode should be activated."""
        result = any(theme in CREATIVE_THEMES for theme in themes)
        print(f"[DecisionLayer] Необходимость активации креативного режима: {result}")
        log_audit_entry(
            "decision_layer_creative_mode_decision",
            "[DecisionLayer] Решение о необходимости активации креативного режима.",
            AuditStatus.INFO,
            details={"result": result},
        )
        return result

    # --------------------------------------------------------------------- #
    #                     VISUAL MODULE HANDLING
    # --------------------------------------------------------------------- #
    def _get_visual_module(self) -> Optional[VisualModule]:
        if self._visual_module_failed:
            return None
        if self._visual_module is None:
            try:
                self._visual_module = VisualModule()
                print("[DecisionLayer] Модуль VisionModule инициализирован.")
                log_audit_entry(
                    "decision_layer_vision_module_init",
                    "[DecisionLayer] Модуль VisionModule инициализирован.",
                    AuditStatus.INFO,
                )
            except Exception as exc:
                print(f"[DecisionLayer] Ошибка инициализации VisionModule: {exc}")
                log_audit_entry(
                    "decision_layer_vision_init_error",
                    "[DecisionLayer] Ошибка инициализации VisionModule.",
                    AuditStatus.ERROR,
                    details={"error": str(exc)},
                )
                self._visual_module_failed = True
                self._visual_module = None
        return self._visual_module

    async def _collect_visual_context(
        self, media_payload: List[Dict[str, Any]], decisions: Dict[str, bool]
    ) -> Dict[str, Any]:
        """Collect visual description of attachments and/or screen snapshot."""
        if not get_config_value("vision.enabled", False):
            print("[DecisionLayer] Визуальный модуль отключен в конфигурации.")
            log_audit_entry(
                "decision_layer_vision_disabled",
                "[DecisionLayer] Визуальный модуль отключен в конфигурации.",
                AuditStatus.INFO,
            )
            return {}

        media_payload = media_payload or []
        has_images = self._has_image_attachments(media_payload)
        needs_vision = decisions.get("needs_vision", False)
        if not needs_vision and not has_images:
            print("[DecisionLayer] Визуальный анализ не требуется — пропускаем.")
            log_audit_entry(
                "decision_layer_vision_skipped",
                "[DecisionLayer] Визуальный анализ пропущен.",
                AuditStatus.INFO,
                details={"needs_vision": needs_vision, "has_images": has_images},
            )
            return {}

        module = self._get_visual_module()
        if not module:
            print("[DecisionLayer] Визуальный модуль недоступен.")
            log_audit_entry(
                "decision_layer_vision_module_unavailable",
                "[DecisionLayer] Визуальный модуль недоступен.",
                AuditStatus.WARNING,
            )
            return {}

        if not module.is_ready():
            print("[DecisionLayer] Визуальный модуль не готов к обработке.")
            log_audit_entry(
                "decision_layer_vision_not_ready",
                "[DecisionLayer] Визуальный модуль не готов к обработке.",
                AuditStatus.WARNING,
            )
            return {}

        # ----------------------------------------------------------------- #
        # Run two potentially heavy visual operations in separate threads
        # ----------------------------------------------------------------- #
        coroutines = [
            (
                asyncio.to_thread(module.describe_media_attachments, media_payload)
                if has_images
                else asyncio.sleep(0, result=None)
            ),
            (
                asyncio.to_thread(module.describe_screen_snapshot)
                if decisions.get("needs_vision", False)
                else asyncio.sleep(0, result=None)
            ),
        ]

        attachments_result, screen_result = await asyncio.gather(
            *coroutines, return_exceptions=True
        )

        # ----------------------------------------------------------------- #
        # Log results (including exceptions, if they occurred)
        # ----------------------------------------------------------------- #
        if isinstance(attachments_result, Exception):
            print(
                f"[DecisionLayer] Ошибка при описании изображений: {attachments_result}"
            )
            log_audit_entry(
                "decision_layer_vision_attachment_error",
                "[DecisionLayer] Ошибка при описании изображений.",
                AuditStatus.ERROR,
                details={"error": str(attachments_result)},
            )
            attachments_result = None
        else:
            print("[DecisionLayer] Описание изображений завершено.")
            log_audit_entry(
                "decision_layer_vision_attachments",
                "[DecisionLayer] Описание изображений завершено.",
                AuditStatus.INFO,
                details={"result": attachments_result},
            )

        if isinstance(screen_result, Exception):
            print(f"[DecisionLayer] Ошибка при описании экрана: {screen_result}")
            log_audit_entry(
                "decision_layer_vision_screen_error",
                "[DecisionLayer] Ошибка при описании экрана.",
                AuditStatus.ERROR,
                details={"error": str(screen_result)},
            )
            screen_result = None
        else:
            print("[DecisionLayer] Описание экрана завершено.")
            log_audit_entry(
                "decision_layer_vision_screen",
                "[DecisionLayer] Описание экрана завершено.",
                AuditStatus.INFO,
                details={"result": screen_result},
            )

        # ----------------------------------------------------------------- #
        # Prepare final visual_context
        # ----------------------------------------------------------------- #
        visual_context: Dict[str, Any] = {}

        if attachments_result:
            updates = attachments_result.get("updates", [])
            for update in updates:
                idx = update.get("index")
                summary = update.get("description")
                if isinstance(idx, int) and summary and 0 <= idx < len(media_payload):
                    media_payload[idx]["description"] = summary
            if attachments_result.get("items"):
                visual_context["attachments"] = attachments_result

        if screen_result and screen_result.get("description"):
            visual_context["screen"] = screen_result

        if visual_context:
            print("[DecisionLayer] Визуальный контекст подготовлен.")
            log_audit_entry(
                "decision_layer_visual_context_prepared",
                "[DecisionLayer] Визуальный контекст подготовлен.",
                AuditStatus.INFO,
                details={
                    "attachments": len(
                        (visual_context.get("attachments", {}) or {}).get("items", [])
                    ),
                    "has_screen": bool(visual_context.get("screen")),
                },
            )

        return visual_context

    @staticmethod
    def _has_image_attachments(media_payload: List[Dict[str, Any]]) -> bool:
        for item in media_payload:
            if (item.get("category") or "").lower() == "image" and item.get("data"):
                return True
        return False


# --------------------------------------------------------------------- #
# Global singleton instance – can be imported everywhere as `decision_layer`
# --------------------------------------------------------------------- #
decision_layer = DecisionLayer()
