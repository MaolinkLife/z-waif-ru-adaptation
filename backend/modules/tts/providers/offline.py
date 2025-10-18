from __future__ import annotations

import os
import tempfile
import time
from typing import Optional

try:
    import pyttsx3

    PYTTSX3_AVAILABLE = True
except ImportError:
    pyttsx3 = None
    PYTTSX3_AVAILABLE = False

from pydub import AudioSegment

from modules.tts.providers.base import TTSProvider, TTSProviderError
from modules.tts.types import TTSRequest, TTSResult
from services.logger_service import AuditStatus, log_audit_entry
from services.localization_service import get_text


class OfflineTTSProvider(TTSProvider):
    name = "offline"

    def __init__(self, voice: Optional[str] = None) -> None:
        self._engine = None
        self._voice = voice

        if not PYTTSX3_AVAILABLE:
            message_pyttsx3_missing = get_text(
                "logger.offline_tts_no_pyttsx3",
                default="[Offline TTS] pyttsx3 not available",
            )
            print(message_pyttsx3_missing)
            log_audit_entry(
                "offline_tts_no_pyttsx3",
                message_pyttsx3_missing,
                AuditStatus.WARNING,
                details={"pyttsx3_installed": False},
                message_key="logger.offline_tts_no_pyttsx3",
            )
            return

        try:
            self._engine = pyttsx3.init()

            # Логирование доступных голосов
            available_voices = []
            if self._engine:
                voices = self._engine.getProperty("voices")
                available_voices = [v.name for v in voices]

                voices_message = get_text(
                    "logger.offline_tts_voices_available",
                    params={"count": len(available_voices)},
                    default="[Offline TTS] Loaded {count} offline voices",
                )
                print(voices_message)
                log_audit_entry(
                    "offline_tts_voices_available",
                    voices_message,
                    AuditStatus.INFO,
                    details={"voices": available_voices, "requested_voice": voice},
                    message_key="logger.offline_tts_voices_available",
                    message_args={"count": len(available_voices)},
                )

                # Установка голоса
                if voice:
                    voice_set = False
                    for voice_obj in voices:
                        if voice in (voice_obj.name, voice_obj.id):
                            self._engine.setProperty("voice", voice_obj.id)
                            voice_set_message = get_text(
                                "logger.offline_tts_voice_set",
                                params={
                                    "voice_name": voice_obj.name,
                                    "voice_id": voice_obj.id,
                                },
                                default="[Offline TTS] Voice set: {voice_name}",
                            )
                            print(voice_set_message)
                            log_audit_entry(
                                "offline_tts_voice_set",
                                voice_set_message,
                                AuditStatus.INFO,
                                details={
                                    "voice_id": voice_obj.id,
                                    "voice_name": voice_obj.name,
                                },
                                message_key="logger.offline_tts_voice_set",
                                message_args={
                                    "voice_name": voice_obj.name,
                                    "voice_id": voice_obj.id,
                                },
                            )
                            voice_set = True
                            break

                    if not voice_set:
                        voice_not_found_message = get_text(
                            "logger.offline_tts_voice_not_found",
                            params={"voice": voice},
                            default="[Offline TTS] Requested voice '{voice}' not found, using default",
                        )
                        print(voice_not_found_message)
                        log_audit_entry(
                            "offline_tts_voice_not_found",
                            voice_not_found_message,
                            AuditStatus.WARNING,
                            details={"requested": voice, "available": available_voices},
                            message_key="logger.offline_tts_voice_not_found",
                            message_args={"voice": voice},
                        )

        except Exception as e:
            init_failed_message = get_text(
                "logger.offline_tts_init_failed",
                params={"error": str(e)},
                default="[Offline TTS] Failed to initialize engine: {error}",
            )
            print(init_failed_message)
            log_audit_entry(
                "offline_tts_init_failed",
                init_failed_message,
                AuditStatus.ERROR,
                details={"error": str(e)},
                message_key="logger.offline_tts_init_failed",
                message_args={"error": str(e)},
            )
            self._engine = None

    def is_available(self) -> bool:
        available = self._engine is not None
        availability_message = get_text(
            "logger.offline_tts_availability_check",
            params={"available": available},
            default=f"[Offline TTS] Availability: {available}",
        )
        print(availability_message)
        log_audit_entry(
            "offline_tts_availability_check",
            availability_message,
            AuditStatus.INFO if available else AuditStatus.WARNING,
            message_key="logger.offline_tts_availability_check",
            message_args={"available": available},
        )
        return available

    def synthesize(self, request: TTSRequest, output_path: str) -> TTSResult:
        if not self._engine:
            not_available_message = get_text(
                "logger.offline_tts_not_available",
                default="[Offline TTS] Engine not available for synthesis",
            )
            print(not_available_message)
            log_audit_entry(
                "offline_tts_not_available",
                not_available_message,
                AuditStatus.ERROR,
                details={"request_text": request.text[:50]},
                message_key="logger.offline_tts_not_available",
            )
            raise TTSProviderError("Offline TTS engine is not available")

        synthesis_start_message = get_text(
            "logger.offline_tts_synthesis_start",
            default="[Offline TTS] Starting synthesis",
        )
        print(synthesis_start_message)
        log_audit_entry(
            "offline_tts_synthesis_start",
            synthesis_start_message,
            AuditStatus.INFO,
            details={"text_length": len(request.text), "output_path": output_path},
            message_key="logger.offline_tts_synthesis_start",
        )

        start = time.time()
        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".wav")
        os.close(tmp_fd)

        try:
            # Синтез в WAV файл
            self._engine.save_to_file(request.text, tmp_path)
            self._engine.runAndWait()

            # Конвертация в MP3
            audio = AudioSegment.from_file(tmp_path)
            audio.export(output_path, format="mp3")

            duration_ms = int((time.time() - start) * 1000)
            success_message = get_text(
                "logger.offline_tts_synthesis_success",
                params={"duration_ms": duration_ms},
                default="[Offline TTS] Synthesis completed successfully in {duration_ms} ms",
            )
            print(success_message)
            log_audit_entry(
                "offline_tts_synthesis_success",
                success_message,
                AuditStatus.INFO,
                details={
                    "input_file": tmp_path,
                    "output_file": output_path,
                    "duration_ms": duration_ms,
                },
                message_key="logger.offline_tts_synthesis_success",
                message_args={"duration_ms": duration_ms},
            )

        except Exception as exc:
            failure_message = get_text(
                "logger.offline_tts_synthesis_failed",
                params={"error": str(exc)},
                default="[Offline TTS] Synthesis failed: {error}",
            )
            print(failure_message)
            log_audit_entry(
                "offline_tts_synthesis_failed",
                failure_message,
                AuditStatus.ERROR,
                details={
                    "error": str(exc),
                    "request_text": request.text[:50],
                    "output_path": output_path,
                },
                message_key="logger.offline_tts_synthesis_failed",
                message_args={"error": str(exc)},
            )
            raise TTSProviderError(f"Offline synthesis failed: {exc}") from exc
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                    temp_removed_message = get_text(
                        "logger.offline_tts_temp_file_removed",
                        params={"file": tmp_path},
                        default="[Offline TTS] Removed temporary file {file}",
                    )
                    print(temp_removed_message)
                    log_audit_entry(
                        "offline_tts_temp_file_removed",
                        temp_removed_message,
                        AuditStatus.INFO,
                        message_key="logger.offline_tts_temp_file_removed",
                        message_args={"file": tmp_path},
                    )
                except OSError as e:
                    temp_remove_error_message = get_text(
                        "logger.offline_tts_temp_file_remove_error",
                        params={"error": str(e), "file": tmp_path},
                        default="[Offline TTS] Failed to remove temporary file {file}: {error}",
                    )
                    print(temp_remove_error_message)
                    log_audit_entry(
                        "offline_tts_temp_file_remove_error",
                        temp_remove_error_message,
                        AuditStatus.WARNING,
                        details={"error": str(e), "file": tmp_path},
                        message_key="logger.offline_tts_temp_file_remove_error",
                        message_args={"error": str(e), "file": tmp_path},
                    )

        duration_ms = int((time.time() - start) * 1000)
        return TTSResult(
            success=True,
            provider=self.name,
            file_path=output_path,
            duration_ms=duration_ms,
        )

    def shutdown(self) -> None:
        if self._engine:
            try:
                self._engine.stop()
                shutdown_message = get_text(
                    "logger.offline_tts_shutdown",
                    default="[Offline TTS] Engine stopped",
                )
                print(shutdown_message)
                log_audit_entry(
                    "offline_tts_shutdown",
                    shutdown_message,
                    AuditStatus.INFO,
                    message_key="logger.offline_tts_shutdown",
                )
            except Exception as e:
                shutdown_error_message = get_text(
                    "logger.offline_tts_shutdown_error",
                    params={"error": str(e)},
                    default="[Offline TTS] Error during shutdown: {error}",
                )
                print(shutdown_error_message)
                log_audit_entry(
                    "offline_tts_shutdown_error",
                    shutdown_error_message,
                    AuditStatus.WARNING,
                    details={"error": str(e)},
                    message_key="logger.offline_tts_shutdown_error",
                    message_args={"error": str(e)},
                )
