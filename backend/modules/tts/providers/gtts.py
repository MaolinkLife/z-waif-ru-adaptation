"""gTTS provider with pyttsx3 fallback support."""

from __future__ import annotations

import os
import tempfile
import time
from typing import Any, Dict, List, Optional

try:
    from gtts import gTTS

    GTTS_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    gTTS = None
    GTTS_AVAILABLE = False

from modules.tts.providers.base import TTSProvider, TTSProviderError
from modules.tts.providers.offline import OfflineTTSProvider
from modules.tts.types import TTSRequest, TTSResult
from services.logger_service import AuditStatus, log_audit_entry


def _as_bool(value: Any) -> bool:
    """Utility to normalize truthy configuration flags."""

    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


class GTTSProvider(TTSProvider):
    """Primary gTTS provider with automatic fallback to pyttsx3."""

    name = "gtts"

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        self._config = config or {}
        self._language = self._config.get("language", "ru")
        self._tld = self._config.get("tld", "com")
        self._slow = _as_bool(self._config.get("slow", False))
        self._fallback_voice = self._config.get("fallback_voice")
        self._offline_provider: Optional[OfflineTTSProvider] = None
        self._offline_initialized = False

        print("[GTTSProvider] Запущен модуль gTTS, запустили проверку конфигурации.")
        log_audit_entry(
            "gtts_provider_init",
            "[GTTSProvider/Init] Провайдер gTTS инициализирован.",
            AuditStatus.INFO,
            details={
                "language": self._language,
                "tld": self._tld,
                "slow": self._slow,
                "fallback_voice": self._fallback_voice,
                "gtts_installed": GTTS_AVAILABLE,
            },
        )

        if not GTTS_AVAILABLE:
            print("[GTTSProvider] Библиотека gTTS не найдена, будет использован fallback.")
            log_audit_entry(
                "gtts_library_missing",
                "[GTTSProvider/Init] gTTS недоступен, активируем fallback.",
                AuditStatus.WARNING,
                details={"gtts_installed": GTTS_AVAILABLE},
            )

    def _ensure_offline_provider(self) -> Optional[OfflineTTSProvider]:
        """Initialize the offline provider lazily with detailed logging."""

        if self._offline_initialized:
            return self._offline_provider

        self._offline_initialized = True
        print("[GTTSProvider] Инициализация fallback-провайдера pyttsx3.")
        log_audit_entry(
            "gtts_fallback_init",
            "[GTTSProvider/Fallback] Инициализация pyttsx3 fallback.",
            AuditStatus.INFO,
            details={"fallback_voice": self._fallback_voice},
        )

        try:
            self._offline_provider = OfflineTTSProvider(voice=self._fallback_voice)
        except Exception as exc:  # pragma: no cover - defensive
            print(
                "[GTTSProvider] Ошибка при инициализации pyttsx3 fallback:",
                str(exc),
            )
            log_audit_entry(
                "gtts_fallback_init_failed",
                "[GTTSProvider/Fallback] Ошибка инициализации pyttsx3 fallback.",
                AuditStatus.ERROR,
                details={"error": str(exc)},
            )
            self._offline_provider = None

        return self._offline_provider

    def is_available(self) -> bool:
        print("[GTTSProvider] Выполняем проверку доступности gTTS и fallback.")
        fallback = self._ensure_offline_provider()
        fallback_available = bool(fallback and fallback.is_available())
        available = GTTS_AVAILABLE or fallback_available

        log_audit_entry(
            "gtts_availability_check",
            "[GTTSProvider/Availability] Проверка доступности провайдера.",
            AuditStatus.INFO if available else AuditStatus.WARNING,
            details={
                "gtts_installed": GTTS_AVAILABLE,
                "fallback_available": fallback_available,
            },
        )
        return available

    def synthesize(self, request: TTSRequest, output_path: str) -> TTSResult:
        print("[GTTSProvider] Начинаем синтез текста, собираем анализ перед отправкой.")
        start_time = time.time()
        attempts: List[str] = []

        log_audit_entry(
            "gtts_synthesis_start",
            "[GTTSProvider/Synthesis] Старт синтеза речи.",
            AuditStatus.INFO,
            details={
                "text_length": len(request.text),
                "text_preview": (
                    request.text[:100] + "..."
                    if len(request.text) > 100
                    else request.text
                ),
                "language": self._language,
                "slow": self._slow,
                "target_path": output_path,
            },
        )

        primary_error: Optional[str] = None
        tmp_path: Optional[str] = None

        if GTTS_AVAILABLE:
            attempts.append("gtts")
            try:
                fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
                os.close(fd)

                print("[GTTSProvider] Выполняем генерацию через gTTS.")
                log_audit_entry(
                    "gtts_primary_attempt",
                    "[GTTSProvider/Synthesis] Попытка синтеза через gTTS.",
                    AuditStatus.INFO,
                    details={
                        "temp_path": tmp_path,
                        "language": self._language,
                        "tld": self._tld,
                        "slow": self._slow,
                    },
                )

                tts = gTTS(
                    text=request.text,
                    lang=self._language,
                    slow=self._slow,
                    tld=self._tld,
                )
                tts.save(tmp_path)
                os.replace(tmp_path, output_path)
                duration_ms = int((time.time() - start_time) * 1000)

                print("[GTTSProvider] Синтез через gTTS выполнен успешно.")
                log_audit_entry(
                    "gtts_primary_success",
                    "[GTTSProvider/Synthesis] Синтез gTTS завершён.",
                    AuditStatus.SUCCESS,
                    details={
                        "output_path": output_path,
                        "duration_ms": duration_ms,
                        "attempts": attempts,
                    },
                )

                return TTSResult(
                    success=True,
                    file_path=output_path,
                    duration_ms=duration_ms,
                    attempted_engines=attempts,
                )
            except Exception as exc:
                primary_error = str(exc)
                print("[GTTSProvider] Ошибка синтеза через gTTS:", primary_error)
                log_audit_entry(
                    "gtts_primary_failed",
                    "[GTTSProvider/Synthesis] Ошибка синтеза через gTTS.",
                    AuditStatus.ERROR,
                    details={
                        "error": primary_error,
                        "attempts": attempts,
                        "had_temp_file": bool(tmp_path),
                    },
                )
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    try:
                        os.remove(tmp_path)
                        log_audit_entry(
                            "gtts_temp_cleanup",
                            "[GTTSProvider/Synthesis] Удаление временного файла.",
                            AuditStatus.INFO,
                            details={"temp_path": tmp_path},
                        )
                    except OSError as exc:
                        log_audit_entry(
                            "gtts_temp_cleanup_failed",
                            "[GTTSProvider/Synthesis] Не удалось удалить временный файл.",
                            AuditStatus.WARNING,
                            details={"temp_path": tmp_path, "error": str(exc)},
                        )
        else:
            primary_error = "gTTS library is not installed"
            log_audit_entry(
                "gtts_primary_skipped",
                "[GTTSProvider/Synthesis] gTTS недоступен, переходим к fallback.",
                AuditStatus.WARNING,
                details={"reason": primary_error},
            )

        fallback_provider = self._ensure_offline_provider()
        if fallback_provider and fallback_provider.is_available():
            attempts.append("pyttsx3")
            print("[GTTSProvider] Запускаем fallback синтез через pyttsx3.")
            log_audit_entry(
                "gtts_fallback_attempt",
                "[GTTSProvider/Fallback] Запуск fallback через pyttsx3.",
                AuditStatus.INFO,
                details={
                    "reason": primary_error,
                    "attempts": attempts,
                },
            )

            try:
                result = fallback_provider.synthesize(request, output_path)
                result.attempted_engines = attempts
                result.fallback_used = True

                log_audit_entry(
                    "gtts_fallback_success",
                    "[GTTSProvider/Fallback] pyttsx3 fallback завершился успешно.",
                    AuditStatus.SUCCESS,
                    details={
                        "output_path": output_path,
                        "duration_ms": result.duration_ms,
                        "attempts": attempts,
                    },
                )
                return result
            except TTSProviderError as fallback_error:
                fallback_message = str(fallback_error)
                print(
                    "[GTTSProvider] Fallback pyttsx3 завершился с ошибкой:",
                    fallback_message,
                )
                log_audit_entry(
                    "gtts_fallback_failed",
                    "[GTTSProvider/Fallback] Ошибка синтеза через pyttsx3.",
                    AuditStatus.ERROR,
                    details={
                        "primary_error": primary_error,
                        "fallback_error": fallback_message,
                        "attempts": attempts,
                    },
                )
                raise TTSProviderError(
                    f"gTTS failed ({primary_error}) and fallback failed ({fallback_message})"
                ) from fallback_error

        print(
            "[GTTSProvider] Все попытки синтеза не удались, нет доступного fallback.",
            primary_error,
        )
        log_audit_entry(
            "gtts_no_fallback_available",
            "[GTTSProvider/Fallback] Нет доступного fallback для синтеза.",
            AuditStatus.ERROR,
            details={
                "primary_error": primary_error,
                "attempts": attempts,
            },
        )

        raise TTSProviderError(
            primary_error or "Neither gTTS nor pyttsx3 fallback could synthesize audio"
        )

    def shutdown(self) -> None:
        print("[GTTSProvider] Завершение работы провайдера gTTS.")
        if self._offline_provider:
            self._offline_provider.shutdown()
            log_audit_entry(
                "gtts_shutdown_fallback",
                "[GTTSProvider/Shutdown] Остановлен pyttsx3 fallback.",
                AuditStatus.INFO,
            )
        log_audit_entry(
            "gtts_shutdown",
            "[GTTSProvider/Shutdown] Провайдер gTTS остановлен.",
            AuditStatus.INFO,
        )
