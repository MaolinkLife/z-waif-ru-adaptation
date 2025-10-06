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


class OfflineTTSProvider(TTSProvider):
    name = "offline"

    def __init__(self, voice: Optional[str] = None) -> None:
        self._engine = None
        self._voice = voice

        if not PYTTSX3_AVAILABLE:
            log_audit_entry(
                "offline_tts_no_pyttsx3",
                "[Offline TTS] pyttsx3 not available",
                AuditStatus.WARNING,
                details={"pyttsx3_installed": False},
            )
            return

        try:
            self._engine = pyttsx3.init()

            # Логирование доступных голосов
            available_voices = []
            if self._engine:
                voices = self._engine.getProperty("voices")
                available_voices = [v.name for v in voices]

                log_audit_entry(
                    "offline_tts_voices_available",
                    "[Offline TTS] Available voices",
                    AuditStatus.INFO,
                    details={"voices": available_voices, "requested_voice": voice},
                )

                # Установка голоса
                if voice:
                    voice_set = False
                    for voice_obj in voices:
                        if voice in (voice_obj.name, voice_obj.id):
                            self._engine.setProperty("voice", voice_obj.id)
                            log_audit_entry(
                                "offline_tts_voice_set",
                                "[Offline TTS] Voice set successfully",
                                AuditStatus.INFO,
                                details={
                                    "voice_id": voice_obj.id,
                                    "voice_name": voice_obj.name,
                                },
                            )
                            voice_set = True
                            break

                    if not voice_set:
                        log_audit_entry(
                            "offline_tts_voice_not_found",
                            "[Offline TTS] Requested voice not found, using default",
                            AuditStatus.WARNING,
                            details={"requested": voice, "available": available_voices},
                        )

        except Exception as e:
            log_audit_entry(
                "offline_tts_init_failed",
                "[Offline TTS] Failed to initialize engine",
                AuditStatus.ERROR,
                details={"error": str(e)},
            )
            self._engine = None

    def is_available(self) -> bool:
        available = self._engine is not None
        log_audit_entry(
            "offline_tts_availability_check",
            f"[Offline TTS] Availability: {available}",
            AuditStatus.INFO if available else AuditStatus.WARNING,
        )
        return available

    def synthesize(self, request: TTSRequest, output_path: str) -> TTSResult:
        if not self._engine:
            log_audit_entry(
                "offline_tts_not_available",
                "[Offline TTS] Engine not available for synthesis",
                AuditStatus.ERROR,
                details={"request_text": request.text[:50]},
            )
            raise TTSProviderError("Offline TTS engine is not available")

        log_audit_entry(
            "offline_tts_synthesis_start",
            "[Offline TTS] Starting synthesis",
            AuditStatus.INFO,
            details={"text_length": len(request.text), "output_path": output_path},
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

            log_audit_entry(
                "offline_tts_synthesis_success",
                "[Offline TTS] Synthesis completed successfully",
                AuditStatus.INFO,
                details={
                    "input_file": tmp_path,
                    "output_file": output_path,
                    "duration_ms": int((time.time() - start) * 1000),
                },
            )

        except Exception as exc:
            log_audit_entry(
                "offline_tts_synthesis_failed",
                "[Offline TTS] Synthesis failed",
                AuditStatus.ERROR,
                details={
                    "error": str(exc),
                    "request_text": request.text[:50],
                    "output_path": output_path,
                },
            )
            raise TTSProviderError(f"Offline synthesis failed: {exc}") from exc
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                    log_audit_entry(
                        "offline_tts_temp_file_removed",
                        "[Offline TTS] Removed temporary file",
                        AuditStatus.INFO,
                    )
                except OSError as e:
                    log_audit_entry(
                        "offline_tts_temp_file_remove_error",
                        "[Offline TTS] Failed to remove temporary file",
                        AuditStatus.WARNING,
                        details={"error": str(e), "file": tmp_path},
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
                log_audit_entry(
                    "offline_tts_shutdown",
                    "[Offline TTS] Engine stopped",
                    AuditStatus.INFO,
                )
            except Exception as e:
                log_audit_entry(
                    "offline_tts_shutdown_error",
                    "[Offline TTS] Error during shutdown",
                    AuditStatus.WARNING,
                    details={"error": str(e)},
                )
