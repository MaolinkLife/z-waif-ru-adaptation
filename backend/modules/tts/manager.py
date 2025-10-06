from __future__ import annotations

import os
import queue
import threading
import tempfile
import time

from modules.tts import audio

from collections import deque
from typing import Deque, Dict, List, Optional, Set, Tuple

from utils.sentence_splitter import split_into_sentences
from modules.tts.audio import AudioPlayback
from modules.tts.providers.base import TTSProvider, TTSProviderError
from modules.tts.providers.edge import EdgeTTSProvider
from modules.tts.providers.elevenlabs import ElevenLabsProvider
from modules.tts.providers.gtts import GTTSProvider
from modules.tts.providers.offline import OfflineTTSProvider
from modules.tts.state import VoiceStage, voice_state
from modules.tts.types import TTSRequest, TTSResult
from services.config_service import get_config_value
from services.logger_service import AuditStatus, log_audit_entry


def _as_bool(value: object) -> bool:
    """
    Convert various types to boolean.

    Args:
        value: Input value to convert

    Returns:
        bool: Converted boolean value
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def _normalize_text(value: str) -> str:
    """
    Normalize text by converting to lowercase and replacing multiple spaces with single space.

    Args:
        value: Input text to normalize

    Returns:
        str: Normalized text
    """
    import re

    return re.sub(r"\s+", " ", (value or "").strip().lower())


def _clean_text(text: str) -> str:
    """
    Clean text by removing markdown formatting, emojis, and hashtags.

    Args:
        text: Input text to clean

    Returns:
        str: Cleaned text
    """
    import re
    import emoji

    text = re.sub(r"\*(.*?)\*", "", text).strip()
    text = emoji.replace_emoji(text, replace="")
    text = text.replace("#", "")
    return text


class TTSManager:
    """
    Text-to-Speech Manager that handles audio synthesis, playback, and provider management.

    This class manages multiple TTS providers with fallback capabilities, maintains
    a queue for speech requests, and handles audio playback with interruption support.
    It also includes mechanisms to prevent self-triggering and track recent outputs.
    """

    def __init__(self) -> None:
        """
        Initialize the TTS Manager with all required components.

        Sets up audio playback, provider management, queue system, and threading
        mechanisms for handling TTS requests.
        """
        log_audit_entry(
            "tts_manager_init",
            "[TTS] Initializing TTS Manager",
            AuditStatus.INFO,
            details={"timestamp": time.time()},
        )

        self._audio = AudioPlayback()
        self._recent_outputs: Deque[Tuple[str, float]] = deque(maxlen=5)
        self._queue: "queue.Queue[Tuple[TTSRequest, bool]]" = queue.Queue()
        self._interrupt = threading.Event()
        self._worker_stop = threading.Event()
        self._providers_lock = threading.Lock()
        self._provider_state_lock = threading.Lock()
        self._providers: Dict[str, TTSProvider] = self._build_providers()
        self._failed_providers: Dict[str, float] = {}

        retry_cfg = get_config_value("voice.provider_retry_seconds", 0) or 0
        try:
            self._provider_retry_seconds = max(0.0, float(retry_cfg))
        except (TypeError, ValueError):
            self._provider_retry_seconds = 0.0

        log_audit_entry(
            "tts_manager_retry_config",
            "[TTS] Provider retry configuration set",
            AuditStatus.INFO,
            details={
                "retry_seconds": self._provider_retry_seconds,
                "config_value": retry_cfg,
            },
        )

        self._worker = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker.start()

        log_audit_entry(
            "tts_manager_started",
            "[TTS] TTS Manager started successfully",
            AuditStatus.INFO,
        )

    def _build_providers(self) -> Dict[str, TTSProvider]:
        """
        Build and return dictionary of available TTS providers.

        Returns:
            Dict[str, TTSProvider]: Dictionary mapping provider names to provider instances
        """
        log_audit_entry(
            "tts_build_providers", "[TTS] Building TTS providers", AuditStatus.INFO
        )

        voice_cfg = get_config_value("voice.voice_modules", {}) or {}
        providers: Dict[str, TTSProvider] = {}

        edge_cfg = voice_cfg.get("edge", {}) or {}
        providers["edge"] = EdgeTTSProvider(
            default_voice=edge_cfg.get("voice_language", "en-US-JennyNeural")
        )

        log_audit_entry(
            "tts_provider_created",
            "[TTS] Edge TTS provider created",
            AuditStatus.INFO,
            details={"voice": edge_cfg.get("voice_language", "en-US-JennyNeural")},
        )

        providers["elevenlabs"] = ElevenLabsProvider(voice_cfg.get("elevenlabs", {}))
        log_audit_entry(
            "tts_provider_created",
            "[TTS] ElevenLabs TTS provider created",
            AuditStatus.INFO,
        )

        print("[TTSManager] Регистрируем провайдера gTTS с fallback на pyttsx3.")
        gtts_cfg = dict(voice_cfg.get("gtts", {}) or {})
        fallback_voice = voice_cfg.get("offline", {}).get("voice")
        if fallback_voice and "fallback_voice" not in gtts_cfg:
            gtts_cfg["fallback_voice"] = fallback_voice
            log_audit_entry(
                "tts_gtts_fallback_voice_sourced",
                "[TTS] Автоматически подставили голос fallback для gTTS.",
                AuditStatus.INFO,
                details={"fallback_voice": fallback_voice},
            )

        providers["gtts"] = GTTSProvider(gtts_cfg)
        log_audit_entry(
            "tts_provider_created",
            "[TTS] gTTS provider created",
            AuditStatus.INFO,
            details={
                "language": gtts_cfg.get("language"),
                "tld": gtts_cfg.get("tld"),
                "slow": gtts_cfg.get("slow"),
                "fallback_voice": gtts_cfg.get("fallback_voice"),
            },
        )

        providers["offline"] = OfflineTTSProvider(
            voice_cfg.get("offline", {}).get("voice")
        )
        log_audit_entry(
            "tts_provider_created",
            "[TTS] Offline TTS provider created",
            AuditStatus.INFO,
            details={"voice": voice_cfg.get("offline", {}).get("voice")},
        )

        return providers

    def _get_providers(self) -> Dict[str, TTSProvider]:
        """
        Get available TTS providers with thread-safe access.

        Returns:
            Dict[str, TTSProvider]: Dictionary of TTS providers
        """
        with self._providers_lock:
            if not self._providers:
                log_audit_entry(
                    "tts_rebuild_providers",
                    "[TTS] Rebuilding providers due to empty cache",
                    AuditStatus.WARNING,
                )
                self._providers = self._build_providers()
        return self._providers

    def _mark_provider_failed(self, name: str, error: str) -> None:
        """
        Mark a provider as failed and log the failure.

        Args:
            name: Name of the failed provider
            error: Error message describing the failure
        """
        with self._provider_state_lock:
            already_failed = name in self._failed_providers
            self._failed_providers[name] = time.time()

        log_audit_entry(
            "voice_provider_disabled",
            (
                "[Voice] Provider disabled after failure."
                if not already_failed
                else "[Voice] Provider failure repeated"
            ),
            AuditStatus.WARNING if not already_failed else AuditStatus.ERROR,
            details={
                "provider": name,
                "error": error,
                "already_failed": already_failed,
            },
        )

    def _clear_provider_failure(self, name: str) -> None:
        """
        Clear failure status for a provider after successful operation.

        Args:
            name: Name of the provider to clear failure status for
        """
        with self._provider_state_lock:
            recovered = name in self._failed_providers
            if recovered:
                del self._failed_providers[name]

        if recovered:
            log_audit_entry(
                "voice_provider_recovered",
                "[Voice] Provider recovered after previous failure.",
                AuditStatus.INFO,
                details={"provider": name},
            )

    def _is_provider_disabled(self, name: str) -> bool:
        """
        Check if a provider is currently disabled due to previous failures.

        Args:
            name: Name of the provider to check

        Returns:
            bool: True if provider is disabled, False otherwise
        """
        with self._provider_state_lock:
            failed_at = self._failed_providers.get(name)
            if failed_at is None:
                return False

            time_since_failure = time.time() - failed_at
            should_retry = (
                self._provider_retry_seconds > 0
                and time_since_failure >= self._provider_retry_seconds
            )

            if should_retry:
                del self._failed_providers[name]
                log_audit_entry(
                    "voice_provider_retry",
                    "[Voice] Retrying provider after cooldown.",
                    AuditStatus.INFO,
                    details={
                        "provider": name,
                        "time_since_failure": time_since_failure,
                    },
                )
                return False
            return True

    def _log_provider_sequence(
        self,
        ordered: List[str],
        active_sequence: List[str],
        skipped: List[str],
        *,
        suppressed: Optional[List[str]] = None,
        remote_fallback_enabled: bool = False,
    ) -> None:
        """
        Log the sequence of TTS providers being used.

        Args:
            ordered: List of provider names in order they were considered
            active_sequence: List of provider names that are active
            skipped: List of provider names that were skipped
            suppressed: List of provider names that were suppressed
            remote_fallback_enabled: Whether remote fallback is enabled
        """
        details = {
            "ordered": ordered,
            "usable": active_sequence,
            "skipped": skipped,
            "remote_fallback_enabled": remote_fallback_enabled,
            "retry_seconds": self._provider_retry_seconds,
        }
        if suppressed:
            details["suppressed"] = suppressed

        log_audit_entry(
            "voice_provider_sequence",
            "[Voice] Provider sequence prepared.",
            AuditStatus.INFO,
            details=details,
        )

    def _log_provider_attempt(self, name: str) -> None:
        """
        Log when a TTS provider is being attempted.

        Args:
            name: Name of the provider being attempted
        """
        log_audit_entry(
            "voice_provider_attempt",
            "[Voice] Trying TTS provider.",
            AuditStatus.INFO,
            details={"provider": name},
        )

    def _log_provider_skip(self, name: str, reason: str) -> None:
        """
        Log when a TTS provider is being skipped.

        Args:
            name: Name of the skipped provider
            reason: Reason for skipping the provider
        """
        log_audit_entry(
            "voice_provider_skipped",
            "[Voice] Provider skipped.",
            AuditStatus.INFO,
            details={"provider": name, "reason": reason},
        )

    def _log_provider_success(self, name: str, duration_ms: Optional[int]) -> None:
        """
        Log when a TTS provider successfully generates speech.

        Args:
            name: Name of the successful provider
            duration_ms: Duration of the generated speech in milliseconds
        """
        log_audit_entry(
            "voice_provider_success",
            "[Voice] Provider produced speech.",
            AuditStatus.INFO,
            details={"provider": name, "duration_ms": duration_ms},
        )

    def _provider_sequence(self) -> List[TTSProvider]:
        """
        Determine the sequence of TTS providers to use based on configuration and availability.

        Returns:
            List[TTSProvider]: List of available TTS providers in order of preference
        """
        log_audit_entry(
            "tts_get_provider_sequence",
            "[TTS] Getting provider sequence",
            AuditStatus.INFO,
        )

        providers = self._get_providers()
        active = get_config_value("voice.active_module", "edge")
        remote_fallback_flag = get_config_value("voice.enable_remote_fallback", False)
        remote_fallback_enabled = _as_bool(remote_fallback_flag)

        order: List[str] = []
        seen: Set[str] = set()

        def add_provider(name: Optional[str]) -> None:
            if name and name in providers and name not in seen:
                order.append(name)
                seen.add(name)

        add_provider(active)
        add_provider("gtts")
        add_provider("offline")

        suppressed: List[str] = []
        if remote_fallback_enabled:
            for name in providers.keys():
                add_provider(name)
        else:
            order_snapshot = set(order)
            suppressed = [
                name
                for name in providers.keys()
                if name not in order_snapshot and name not in ("offline", "gtts", active)
            ]

        if not order:
            for name in providers.keys():
                add_provider(name)

        sequence: List[TTSProvider] = []
        skipped: List[str] = []
        for name in order:
            provider = providers.get(name)
            if not provider:
                continue
            if self._is_provider_disabled(name):
                skipped.append(name)
                continue
            sequence.append(provider)

        if skipped:
            for skipped_name in skipped:
                self._log_provider_skip(skipped_name, "provider_marked_unhealthy")

        self._log_provider_sequence(
            order,
            [p.name for p in sequence],
            skipped,
            suppressed=suppressed,
            remote_fallback_enabled=remote_fallback_enabled,
        )

        log_audit_entry(
            "tts_provider_sequence_result",
            "[TTS] Provider sequence determined",
            AuditStatus.INFO,
            details={
                "active": active,
                "remote_fallback": remote_fallback_enabled,
                "sequence_count": len(sequence),
                "providers": [p.name for p in sequence],
            },
        )

        return sequence

    def synthesize_to_file(self, request: TTSRequest, output_path: str) -> TTSResult:
        """
        Synthesize text to an audio file using available TTS providers.

        Args:
            request: TTS request containing text to synthesize
            output_path: Path where the audio file should be saved

        Returns:
            TTSResult: Result containing success status, error info, and provider details
        """
        log_audit_entry(
            "tts_synthesize_start",
            "[TTS] Starting synthesis to file",
            AuditStatus.INFO,
            details={
                "output_path": output_path,
                "text_length": len(request.text),
                "request_id": getattr(request, "id", "unknown"),
            },
        )

        if not get_config_value("voice.enabled", False):
            log_audit_entry(
                "tts_synthesize_disabled",
                "[TTS] Voice synthesis is disabled",
                AuditStatus.WARNING,
                details={"output_path": output_path},
            )
            return TTSResult(success=False, error="voice_disabled")

        sequence = self._provider_sequence()

        if not sequence:
            with self._provider_state_lock:
                failed = list(self._failed_providers.keys())
            log_audit_entry(
                "voice_no_providers_available",
                "[Voice] No TTS providers available after filtering.",
                AuditStatus.ERROR,
                details={"failed": failed},
            )
            return TTSResult(success=False, error="no_provider_available")

        last_error: Optional[str] = None
        primary_name = sequence[0].name if sequence else None

        log_audit_entry(
            "tts_synthesize_trying_providers",
            "[TTS] Attempting synthesis with providers",
            AuditStatus.INFO,
            details={
                "providers": [p.name for p in sequence],
                "primary": primary_name,
                "total_providers": len(sequence),
            },
        )

        for provider in sequence:
            self._log_provider_attempt(provider.name)
            if not provider.is_available():
                log_audit_entry(
                    "voice_provider_unavailable",
                    "[Voice] Provider unavailable",
                    AuditStatus.WARNING,
                    details={"provider": provider.name},
                )
                last_error = f"{provider.name}_unavailable"
                self._mark_provider_failed(provider.name, "unavailable")
                continue

            try:
                log_audit_entry(
                    "tts_provider_synthesizing",
                    "[TTS] Provider synthesizing text",
                    AuditStatus.INFO,
                    details={
                        "provider": provider.name,
                        "text_length": len(request.text),
                    },
                )

                result = provider.synthesize(request, output_path)
                result.provider = provider.name
                result.fallback_used = provider.name != primary_name

                self._record_output(request.text)
                self._clear_provider_failure(provider.name)
                self._log_provider_success(
                    provider.name, getattr(result, "duration_ms", None)
                )

                log_audit_entry(
                    "tts_synthesize_success",
                    "[TTS] Synthesis completed successfully",
                    AuditStatus.INFO,
                    details={
                        "provider": provider.name,
                        "output_path": output_path,
                        "duration_ms": getattr(result, "duration_ms", None),
                        "fallback_used": result.fallback_used,
                    },
                )

                return result
            except TTSProviderError as exc:
                last_error = str(exc)
                log_audit_entry(
                    "voice_provider_error",
                    "[Voice] Provider error during synthesis",
                    AuditStatus.ERROR,
                    details={"provider": provider.name, "error": last_error},
                )
                self._mark_provider_failed(provider.name, last_error)
                if os.path.exists(output_path):
                    try:
                        os.remove(output_path)
                        log_audit_entry(
                            "tts_temp_file_removed",
                            "[TTS] Removed temporary file after error",
                            AuditStatus.INFO,
                            details={"path": output_path},
                        )
                    except OSError as e:
                        log_audit_entry(
                            "tts_temp_file_remove_error",
                            "[TTS] Failed to remove temporary file",
                            AuditStatus.WARNING,
                            details={"path": output_path, "error": str(e)},
                        )

        log_audit_entry(
            "tts_synthesize_failed",
            "[TTS] All providers failed to synthesize",
            AuditStatus.ERROR,
            details={
                "output_path": output_path,
                "last_error": last_error,
                "attempted_engines": [p.name for p in sequence],
            },
        )

        return TTSResult(
            success=False,
            error=last_error,
            attempted_engines=[p.name for p in sequence],
        )

    def speak(self, text: str, refuse_pause: bool = False) -> TTSResult:
        """
        Speak text immediately without queuing.

        Args:
            text: Text to speak
            refuse_pause: Whether to refuse pauses between sentences

        Returns:
            TTSResult: Result of the speaking operation
        """
        log_audit_entry(
            "tts_speak_immediate",
            "[TTS] Speaking text immediately",
            AuditStatus.INFO,
            details={"text_length": len(text), "refuse_pause": refuse_pause},
        )

        return self._speak_immediate(text, refuse_pause=refuse_pause)

    def enqueue(self, text: str, refuse_pause: bool = False) -> None:
        """
        Add text to the speaking queue for processing.

        Args:
            text: Text to add to queue
            refuse_pause: Whether to refuse pauses between sentences
        """
        request = TTSRequest(text=text)

        log_audit_entry(
            "tts_enqueue",
            "[TTS] Enqueuing text for speaking",
            AuditStatus.INFO,
            details={
                "text_length": len(text),
                "refuse_pause": refuse_pause,
                "queue_size": self._queue.qsize(),
            },
        )

        self._queue.put((request, refuse_pause))

    def _worker_loop(self) -> None:
        """
        Main worker loop that processes items from the queue.
        Runs in a separate thread to handle queued TTS requests.
        """
        log_audit_entry(
            "tts_worker_started", "[TTS] Worker thread started", AuditStatus.INFO
        )

        while not self._worker_stop.is_set():
            try:
                item = self._queue.get(
                    timeout=1.0
                )  # Use timeout to check stop condition
            except queue.Empty:
                continue
            except Exception as e:
                log_audit_entry(
                    "tts_worker_queue_error",
                    "[TTS] Error getting item from queue",
                    AuditStatus.ERROR,
                    details={"error": str(e)},
                )
                continue

            if item is None:
                log_audit_entry(
                    "tts_worker_stop_signal",
                    "[TTS] Worker received stop signal",
                    AuditStatus.INFO,
                )
                self._queue.task_done()
                break

            request, refuse_pause = item
            try:
                if self._interrupt.is_set():
                    log_audit_entry(
                        "tts_worker_interrupted",
                        "[TTS] Worker interrupted, skipping request",
                        AuditStatus.INFO,
                    )
                    continue

                log_audit_entry(
                    "tts_worker_processing",
                    "[TTS] Worker processing request",
                    AuditStatus.INFO,
                    details={
                        "text_length": len(request.text),
                        "refuse_pause": refuse_pause,
                    },
                )

                self._speak_immediate(request.text, refuse_pause=refuse_pause)
            except Exception as e:
                log_audit_entry(
                    "tts_worker_processing_error",
                    "[TTS] Error processing request in worker",
                    AuditStatus.ERROR,
                    details={"error": str(e), "text": request.text[:50]},
                )
            finally:
                self._queue.task_done()

        log_audit_entry(
            "tts_worker_stopped", "[TTS] Worker thread stopped", AuditStatus.INFO
        )

    def _speak_immediate(self, text: str, refuse_pause: bool = False) -> TTSResult:
        """
        Internal method to speak text immediately without queuing.

        Args:
            text: Text to speak
            refuse_pause: Whether to refuse pauses between sentences

        Returns:
            TTSResult: Result of the speaking operation
        """
        log_audit_entry(
            "tts_speak_immediate_start",
            "[TTS] Starting immediate speaking",
            AuditStatus.INFO,
            details={"original_text_length": len(text), "refuse_pause": refuse_pause},
        )

        cleaned_chunks = [
            chunk
            for chunk in (_clean_text(part) for part in split_into_sentences(text))
            if chunk.strip()
        ]

        log_audit_entry(
            "tts_sentence_splitting",
            "[TTS] Sentence splitting completed",
            AuditStatus.INFO,
            details={
                "original_sentences": len(split_into_sentences(text)),
                "cleaned_chunks": len(cleaned_chunks),
                "text_length": len(text),
            },
        )

        if not cleaned_chunks:
            log_audit_entry(
                "tts_empty_chunks",
                "[TTS] No valid text chunks to speak",
                AuditStatus.WARNING,
                details={"original_text": text},
            )
            return TTSResult(success=False, error="empty_text")

        voice_state.enter_speaking("tts_active")
        self._interrupt.clear()

        log_audit_entry(
            "tts_enter_speaking_state",
            "[TTS] Entered speaking state",
            AuditStatus.INFO,
            details={"chunk_count": len(cleaned_chunks)},
        )

        try:
            last_result: Optional[TTSResult] = None
            for idx, chunk in enumerate(cleaned_chunks, start=1):
                # Check for interruption BEFORE synthesis
                if self._interrupt.is_set():
                    log_audit_entry(
                        "tts_interrupted_before_synthesis",
                        "[TTS] Interrupted before synthesis",
                        AuditStatus.INFO,
                        details={
                            "chunk_index": idx,
                            "chunk_count": len(cleaned_chunks),
                        },
                    )
                    return TTSResult(success=False, error="interrupted")

                tmp_fd, tmp_path = tempfile.mkstemp(suffix=".mp3")
                os.close(tmp_fd)

                try:
                    log_audit_entry(
                        "tts_synthesizing_chunk",
                        "[TTS] Synthesizing text chunk",
                        AuditStatus.INFO,
                        details={
                            "chunk_index": idx,
                            "chunk_total": len(cleaned_chunks),
                            "chunk_length": len(chunk),
                        },
                    )

                    result = self.synthesize_to_file(TTSRequest(text=chunk), tmp_path)
                    last_result = result

                    if not result.success:
                        log_audit_entry(
                            "tts_chunk_synthesis_failed",
                            "[TTS] Chunk synthesis failed",
                            AuditStatus.ERROR,
                            details={
                                "chunk_index": idx,
                                "error": result.error,
                                "attempted_engines": result.attempted_engines,
                            },
                        )
                        return result

                    if self._interrupt.is_set():
                        log_audit_entry(
                            "tts_interrupted_before_playback",
                            "[TTS] Interrupted before playback",
                            AuditStatus.INFO,
                            details={"chunk_index": idx},
                        )
                        return TTSResult(success=False, error="interrupted")

                    log_audit_entry(
                        "tts_playing_chunk",
                        "[TTS] Playing synthesized chunk",
                        AuditStatus.INFO,
                        details={
                            "chunk_index": idx,
                            "file_path": tmp_path,
                            "duration_ms": getattr(result, "duration_ms", None),
                        },
                    )

                    self._audio.play_file(tmp_path, interrupt_event=self._interrupt)

                    if self._interrupt.is_set():
                        log_audit_entry(
                            "tts_interrupted_during_playback",
                            "[TTS] Interrupted during playback",
                            AuditStatus.INFO,
                            details={"chunk_index": idx},
                        )
                        return TTSResult(success=False, error="interrupted")

                    pause_duration = 0.001 if refuse_pause else 0.01
                    time.sleep(pause_duration)

                    log_audit_entry(
                        "tts_chunk_completed",
                        "[TTS] Chunk completed successfully",
                        AuditStatus.INFO,
                        details={"chunk_index": idx, "pause_duration": pause_duration},
                    )

                finally:
                    if os.path.exists(tmp_path):
                        try:
                            os.remove(tmp_path)
                            log_audit_entry(
                                "tts_temp_file_removed",
                                "[TTS] Removed temporary file after playback",
                                AuditStatus.INFO,
                                details={"path": tmp_path},
                            )
                        except OSError as e:
                            log_audit_entry(
                                "tts_temp_file_remove_error",
                                "[TTS] Failed to remove temporary file",
                                AuditStatus.WARNING,
                                details={"path": tmp_path, "error": str(e)},
                            )

            self._record_output(text)

            log_audit_entry(
                "tts_speak_completed",
                "[TTS] Immediate speaking completed",
                AuditStatus.INFO,
                details={
                    "chunk_count": len(cleaned_chunks),
                    "success": last_result.success if last_result else False,
                },
            )

            return last_result or TTSResult(success=True)
        finally:
            voice_state.enter_listening("tts_idle")
            log_audit_entry(
                "tts_exit_speaking_state",
                "[TTS] Exited speaking state",
                AuditStatus.INFO,
            )

    def _clear_pending_requests(self) -> int:
        """
        Clear all pending requests from the queue.

        Returns:
            int: Number of requests cleared
        """
        cleared = 0
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            if item is None:
                self._queue.put_nowait(item)
                break
            cleared += 1
            self._queue.task_done()

        log_audit_entry(
            "tts_clear_pending_requests",
            "[TTS] Cleared pending requests from queue",
            AuditStatus.INFO,
            details={"cleared_count": cleared},
        )

        return cleared

    def stop(self) -> None:
        """
        Stop all TTS operations and clear the queue.
        """
        print('[TTSManager] Принят сигнал остановки, инициируем аварийную остановку озвучки.')
        pending_before = self._queue.qsize()
        log_audit_entry(
            'tts_stop_initiated',
            '[TTS] Stopping TTS operations',
            AuditStatus.INFO,
            details={
                'pending_before': pending_before,
                'interrupt_active': self._interrupt.is_set(),
            },
        )

        self._interrupt.set()
        audio.cut_voice = True
        self._audio.stop_all()

        cleared = self._clear_pending_requests()
        print(f"[TTSManager] Очередь очищена, удалено элементов: {cleared}.")

        if self._worker_stop.is_set():
            log_audit_entry(
                'tts_stop_worker_flag_reset',
                '[TTS] Worker stop flag was set; clearing for continued operation.',
                AuditStatus.WARNING,
            )
            self._worker_stop.clear()

        voice_state.enter_listening('tts_stopped')

        log_audit_entry(
            'tts_stop_completed',
            '[TTS] TTS operations stopped',
            AuditStatus.INFO,
            details={
                'cleared_requests': cleared,
                'pending_after': self._queue.qsize(),
            },
        )

    def play_file(self, path: str) -> None:
        """
        Play an audio file directly.

        Args:
            path: Path to the audio file to play
        """
        log_audit_entry(
            "tts_play_file",
            "[TTS] Playing audio file",
            AuditStatus.INFO,
            details={"file_path": path},
        )

        self._audio.play_file(path)

    # ------------------------------------------------------------------
    # Recent output helpers (used by VAD to avoid self-trigger)
    # ------------------------------------------------------------------

    def _record_output(self, text: str) -> None:
        """
        Record output text to prevent self-triggering.

        Args:
            text: Text that was output
        """
        normalized = _normalize_text(text)
        if normalized:
            self._recent_outputs.append((normalized, time.time()))

            log_audit_entry(
                "tts_record_output",
                "[TTS] Recorded output to prevent self-trigger",
                AuditStatus.INFO,
                details={
                    "normalized_text": (
                        normalized[:50] + "..." if len(normalized) > 50 else normalized
                    ),
                    "timestamp": time.time(),
                },
            )

    def matches_recent_output(self, text: str, ttl_seconds: float = 15.0) -> bool:
        """
        Check if text matches recent output to prevent self-triggering.

        Args:
            text: Text to check against recent outputs
            ttl_seconds: Time-to-live in seconds for recent outputs

        Returns:
            bool: True if text matches recent output, False otherwise
        """
        normalized = _normalize_text(text)
        if not normalized:
            return False

        now = time.time()
        matches = any(
            normalized == recorded and (now - ts) <= ttl_seconds
            for recorded, ts in self._recent_outputs
        )

        if matches:
            log_audit_entry(
                "tts_self_trigger_detected",
                "[TTS] Self-trigger detected from recent output",
                AuditStatus.INFO,
                details={
                    "input_text": text[:50] + "..." if len(text) > 50 else text,
                    "matched_text": (
                        normalized[:50] + "..." if len(normalized) > 50 else normalized
                    ),
                },
            )

        return matches

    def log_output(self, text: str) -> None:
        """
        Log output text (alias for _record_output).

        Args:
            text: Text to log as output
        """
        self._record_output(text)

    def shutdown(self) -> None:
        """
        Shutdown the TTS manager and stop all operations.
        """
        log_audit_entry(
            "tts_shutdown_initiated", "[TTS] Initiating shutdown", AuditStatus.INFO
        )

        self._worker_stop.set()
        self._queue.put(None)

        log_audit_entry(
            "tts_shutdown_completed", "[TTS] Shutdown completed", AuditStatus.INFO
        )
