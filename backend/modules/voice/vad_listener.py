import asyncio
import re
import numpy as np
import sounddevice as sd
import webrtcvad
from collections import deque
import uuid
from datetime import datetime
import tempfile
import os
import wave
import json

from services.config_service import get_config_value
from core.decision_layer import decision_layer
from core.instructor import Instructor
from core.websocket_manager import manager
from modules.tts.state import voice_state, VoiceStage
from modules.tts.service import (
    log_last_output,
    is_self_trigger,
    force_cut_voice,
    check_if_speaking,
)
from services import stt_service
from services.api_service import run_stream_message
from services.logger_service import log_audit_entry, AuditStatus


class VADListener:
    def __init__(self):
        self.is_listening = False
        self.audio_buffer = deque()
        self.vad = webrtcvad.Vad(2)  # aggressiveness level 2
        self.speech_detected = False
        self.silence_counter = 0
        self.silence_threshold = 10
        self.vad_threshold = 0.5
        self.sample_rate = 16000
        self.loop = (
            None  # main asyncio loop used to schedule tasks from the audio callback
        )
        self.processing_lock = asyncio.Lock()
        self.active_transcripts: set[str] = set()
        self.last_processed_transcript: str | None = None
        self.last_processed_at: datetime | None = None

    async def start_voice_vad_loop(self):
        """Entry point for the main listening loop."""
        if not get_config_value("voice.enabled", False):
            log_audit_entry(
                event_type="vad_info",
                msg="[VAD] Voice detection disabled in config",
                status=AuditStatus.INFO,
            )
            return

        log_audit_entry(
            event_type="vad_start",
            msg="[VAD] Starting voice detection loop",
            status=AuditStatus.INFO,
        )

        try:
            device_id = get_config_value("audio.input_device_id", 0)
            self.sample_rate = get_config_value("audio.sample_rate", 16000)
            chunk_size = get_config_value("audio.chunk_size", 1024)
            self.vad_threshold = get_config_value("audio.vad_threshold", 0.5)
            silence_timeout = get_config_value("audio.silence_timeout", 3.0)

            if self.sample_rate not in [8000, 16000, 32000, 48000]:
                self.sample_rate = 16000

            self.silence_threshold = int(
                silence_timeout * self.sample_rate / chunk_size
            )
            if self.silence_threshold < 1:
                self.silence_threshold = 10

            self.is_listening = True
            # Remember the current event loop so we can schedule tasks from the callback
            self.loop = asyncio.get_running_loop()

            def audio_callback(indata, frames, time, status):
                if status:
                    log_audit_entry(
                        event_type="vad_audio_status",
                        msg=f"[VAD] Audio callback status: {status}",
                        status=AuditStatus.WARNING,
                        details={"status": str(status)},
                    )

                audio_data = (indata[:, 0] * 32767).astype(np.int16)
                self.process_audio_chunk(audio_data)

            with sd.InputStream(
                device=device_id,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=chunk_size,
                dtype="float32",
                callback=audio_callback,
            ):
                log_audit_entry(
                    event_type="vad_stream_started",
                    msg="[VAD] Audio stream started successfully",
                    status=AuditStatus.SUCCESS,
                    details={
                        "device_id": device_id,
                        "sample_rate": self.sample_rate,
                        "chunk_size": chunk_size,
                    },
                )

                while self.is_listening:
                    await asyncio.sleep(0.01)

        except Exception as e:
            log_audit_entry(
                event_type="vad_error",
                msg=f"[VAD] Error in VAD loop: {str(e)}",
                status=AuditStatus.ERROR,
                details={"error": str(e), "error_type": type(e).__name__},
            )
            raise

    def process_audio_chunk(self, audio_data):
        if not voice_state.is_listening():
            self.reset_detection()
            return

        is_speech = self.is_speech_detected(audio_data)

        if is_speech:
            self.speech_detected = True
            self.silence_counter = 0
            self.audio_buffer.append(audio_data.copy())

            max_buffer_size = int(30 * self.sample_rate / 1024)
            if len(self.audio_buffer) > max_buffer_size:
                self.audio_buffer.popleft()

        elif self.speech_detected:
            self.silence_counter += 1
            self.audio_buffer.append(audio_data.copy())

            if self.silence_counter > self.silence_threshold:
                # Schedule segment processing on the main asyncio loop
                if self.loop is not None:
                    asyncio.run_coroutine_threadsafe(
                        self.process_speech_segment(), self.loop
                    )
                else:
                    # If the loop is not initialized (should not happen), simply reset detection
                    pass

    def is_speech_detected(self, audio_data):
        try:
            frame_duration = 20
            frame_samples = int(self.sample_rate * frame_duration / 1000)

            if len(audio_data) < frame_samples:
                return False

            speech_frames = 0
            total_frames = 0

            for i in range(0, len(audio_data) - frame_samples + 1, frame_samples):
                frame = audio_data[i : i + frame_samples]
                if len(frame) == frame_samples:
                    total_frames += 1
                    if self.vad.is_speech(frame.tobytes(), self.sample_rate):
                        speech_frames += 1

            if total_frames > 0:
                return speech_frames / total_frames > 0.3
            return False

        except Exception as e:
            log_audit_entry(
                event_type="vad_speech_detection_fallback",
                msg=f"[VAD] Speech detection error, falling back to energy: {str(e)}",
                status=AuditStatus.WARNING,
                details={"error": str(e)},
            )
            return self.energy_based_vad(audio_data)

    def energy_based_vad(self, audio_data):
        energy = np.mean(audio_data.astype(np.float32) ** 2)
        normalized_energy = energy / (32767**2)
        return normalized_energy > self.vad_threshold

    def reset_detection(self):
        self.speech_detected = False
        self.silence_counter = 0
        self.audio_buffer.clear()

    async def process_speech_segment(self):
        if not self.audio_buffer:
            return

        try:
            log_audit_entry(
                event_type="vad_speech_segment_start",
                msg="[VAD] Processing speech segment",
                status=AuditStatus.INFO,
                details={"buffer_size": len(self.audio_buffer)},
            )

            audio_segment = np.concatenate(list(self.audio_buffer))

            # Create a temporary WAV file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                temp_filename = tmp_file.name

            try:
                self._save_wave(temp_filename, audio_segment)
                transcript = stt_service.transcribe_audio(temp_filename)

                if transcript and len(transcript.strip()) > 0:
                    await self.handle_transcript(transcript.strip())

            finally:
                if os.path.exists(temp_filename):
                    os.remove(temp_filename)

        except Exception as e:
            log_audit_entry(
                event_type="vad_processing_error",
                msg=f"[VAD] Error processing speech segment: {str(e)}",
                status=AuditStatus.ERROR,
                details={"error": str(e), "error_type": type(e).__name__},
            )
        finally:
            self.reset_detection()

    def _save_wave(self, filename: str, audio: np.ndarray):
        with wave.open(filename, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(self.sample_rate)
            wf.writeframes(audio.tobytes())

    async def handle_transcript(self, transcript):
        log_audit_entry(
            event_type="vad_transcript_received",
            msg="[VAD] Получена расшифровка, проверяем триггеры",
            status=AuditStatus.INFO,
            details={"transcript": transcript},
        )

        if voice_state.stage() != VoiceStage.LISTENING:
            log_audit_entry(
                event_type="vad_stage_blocked",
                msg="[VAD] Стадия не позволяет обрабатывать расшифровку",
                status=AuditStatus.INFO,
                details={"stage": voice_state.stage().value, "transcript": transcript},
            )
            return

        normalized_transcript = self._normalize_text(transcript)
        has_trigger = False

        if self._should_bypass_triggers():
            log_audit_entry(
                event_type="vad_trigger_passthrough",
                msg="[VAD] Пропускаем фильтр триггеров",
                status=AuditStatus.INFO,
                details={"transcript": transcript},
            )
            has_trigger = True
            normalized_transcript = normalized_transcript or transcript
        else:
            has_trigger = self.contains_trigger_word(transcript)

        if not has_trigger:
            log_audit_entry(
                event_type="vad_trigger_miss",
                msg="[VAD] Триггер не найден, пропускаем сообщение",
                status=AuditStatus.INFO,
                details={"transcript": transcript},
            )
            return

        log_audit_entry(
            event_type="vad_trigger_hit",
            msg="[VAD] Триггер найден, готовим сообщение",
            status=AuditStatus.SUCCESS,
            details={"transcript": transcript},
        )

        normalized_transcript = normalized_transcript or self._normalize_text(
            transcript
        )

        if is_self_trigger(transcript):
            log_audit_entry(
                event_type="vad_self_trigger",
                msg="[VAD] Игнорируем: сработал собственный голос",
                status=AuditStatus.INFO,
                details={"transcript": transcript},
            )
            return

        if check_if_speaking():
            log_audit_entry(
                event_type="vad_force_cut_requested",
                msg="[VAD] Персонаж говорит — прерываем текущее воспроизведение",
                status=AuditStatus.INFO,
                details={},
            )
            force_cut_voice()
            await asyncio.sleep(0.1)

        normalized_transcript = self._normalize_text(transcript)
        if self._should_bypass_triggers():
            log_audit_entry(
                event_type="vad_trigger_passthrough",
                msg="[VAD] Пропускаем фильтр триггеров",
                status=AuditStatus.INFO,
                details={"transcript": transcript},
            )
            normalized_transcript = normalized_transcript or transcript
            has_trigger = True
        else:
            has_trigger = self.contains_trigger_word(transcript)

        if not has_trigger:
            log_audit_entry(
                event_type="vad_trigger_miss",
                msg="[VAD] Триггер не найден, пропускаем сообщение",
                status=AuditStatus.INFO,
                details={"transcript": transcript},
            )
            return

        normalized_transcript = normalized_transcript or self._normalize_text(
            transcript
        )
        if not normalized_transcript:
            log_audit_entry(
                event_type="vad_empty_transcript",
                msg="[VAD] Расшифровка пустая после нормализации — пропускаем",
                status=AuditStatus.INFO,
                details={"raw": transcript},
            )
            return

        if normalized_transcript in self.active_transcripts:
            log_audit_entry(
                event_type="vad_duplicate_suppressed",
                msg="[VAD] Дубликат активного запроса подавлен",
                status=AuditStatus.INFO,
                details={"transcript": transcript},
            )
            return
        if (
            self.last_processed_transcript
            and self.last_processed_at
            and self.last_processed_transcript == normalized_transcript
            and (datetime.utcnow() - self.last_processed_at).total_seconds() < 5
        ):
            log_audit_entry(
                event_type="vad_recent_duplicate",
                msg="[VAD] Повторная расшифровка в пределах 5 секунд — пропускаем",
                status=AuditStatus.INFO,
                details={"transcript": transcript},
            )
            return

        voice_state.enter_waiting("generation_in_progress")

        async with self.processing_lock:
            self.active_transcripts.add(normalized_transcript)
            try:
                user_message = {
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "content": transcript,
                    "timestamp": datetime.utcnow().isoformat(),
                }

                message_payload = {
                    "type": "message",
                    "id": user_message["id"],
                    "role": "user",
                    "content": transcript,
                    "timestamp": user_message["timestamp"],
                }
                await manager.send_message(
                    json.dumps(message_payload, ensure_ascii=False)
                )

                instructor = Instructor()
                processing_result = await decision_layer.process_message(
                    user_message, None
                )
                formatted_history = await instructor.format_for_api(
                    processing_result["system_prompt"],
                    processing_result["user_message"],
                )

                async def broadcast_send(payload: dict) -> bool:
                    await manager.send_message(json.dumps(payload, ensure_ascii=False))
                    return True

                await run_stream_message(
                    None, formatted_history, send_fn=broadcast_send
                )
                log_last_output(transcript)
            finally:
                self.active_transcripts.discard(normalized_transcript)
                if voice_state.stage() == VoiceStage.WAITING:
                    voice_state.enter_listening("generation_interrupted")
                self.last_processed_transcript = normalized_transcript
                self.last_processed_at = datetime.utcnow()

    def _should_bypass_triggers(self) -> bool:
        if get_config_value("audio.ignore_trigger_words", False):
            return True
        trigger_words = get_config_value("audio.trigger_words", []) or []
        return len(trigger_words) == 0

    def contains_trigger_word(self, text):
        normalized_text = self._normalize_text(text)
        if not normalized_text:
            return False

        trigger_words = get_config_value("audio.trigger_words", []) or []
        if not trigger_words:
            fallback_name = get_config_value("char_name", "") or ""
            if fallback_name:
                trigger_words = [fallback_name]

        if not trigger_words:
            return False

        tokens = normalized_text.split()
        text_with_boundaries = f" {normalized_text} "

        for raw_trigger in trigger_words:
            normalized_trigger = self._normalize_text(raw_trigger)
            if not normalized_trigger:
                continue

            trigger_tokens = normalized_trigger.split()
            if len(trigger_tokens) == 1:
                if trigger_tokens[0] in tokens:
                    return True
            else:
                phrase = " ".join(trigger_tokens)
                if f" {phrase} " in text_with_boundaries:
                    return True

        return False

    @staticmethod
    def _normalize_text(value: str) -> str:
        if not value:
            return ""

        lowered = value.lower()
        cleaned = re.sub(r"[^\w\s]", " ", lowered, flags=re.UNICODE)
        collapsed = re.sub(r"\s+", " ", cleaned, flags=re.UNICODE).strip()
        return collapsed


vad_listener = VADListener()


async def start_voice_vad_loop():
    await vad_listener.start_voice_vad_loop()


# --- Simple control helpers for VoiceMode (UI buttons) ---
_vad_task = None


async def start_vad_background():
    """Start VAD loop once in background. Returns (started: bool, message)."""
    global _vad_task
    # Respect config flags before spawning
    if not get_config_value("voice.enabled", False) or not get_config_value(
        "audio.enable_vad", False
    ):
        return (
            False,
            "VAD disabled by config (voice.enabled/audio.enable_vad)",
        )

    if vad_listener.is_listening or (_vad_task and not _vad_task.done()):
        return False, "VAD already running"

    _vad_task = asyncio.create_task(start_voice_vad_loop())
    return True, "VAD started"


async def stop_vad(wait: bool = True, timeout: float = 2.0):
    """Signal VAD loop to stop. Optionally wait for task to finish."""
    global _vad_task
    if not vad_listener.is_listening and (not _vad_task or _vad_task.done()):
        return False, "VAD not running"

    vad_listener.is_listening = False
    # Let the loop exit and InputStream close gracefully
    if wait and _vad_task:
        try:
            await asyncio.wait_for(_vad_task, timeout=timeout)
        except Exception:
            # Best-effort: cancel if still pending
            if not _vad_task.done():
                _vad_task.cancel()
    return True, "VAD stopping"


def is_vad_running() -> bool:
    return vad_listener.is_listening
