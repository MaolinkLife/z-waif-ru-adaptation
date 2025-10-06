from __future__ import annotations
import os
import threading
import time
from typing import Iterable, List

import numpy as np
import sounddevice as sd
from pydub import AudioSegment

from services.config_service import get_config_value
from services.logger_service import AuditStatus, log_audit_entry

cut_voice = False


class AudioPlayback:
    def __init__(self) -> None:
        self._active_streams: List[sd.OutputStream] = []
        self._stream_lock = threading.Lock()

    def play_file(self, file_path: str, interrupt_event=None) -> None:
        global cut_voice
        cut_voice = False
        log_audit_entry(
            "voice_play_start", f"Starting playback for: {file_path}", AuditStatus.INFO
        )

        if not os.path.isfile(file_path):
            log_audit_entry(
                "voice_audio_missing",
                f"[Voice] File not found: {file_path}",
                AuditStatus.WARNING,
            )
            return

        sound = AudioSegment.from_file(file_path)
        samples = np.array(sound.get_array_of_samples()).astype(np.float32)
        samples /= np.iinfo(sound.array_type).max

        devices: List[int] = []
        if get_config_value("voice.use_windows_output", True):
            windows_id = get_config_value("voice.windows_output_id", 0)
            if isinstance(windows_id, str):
                try:
                    windows_id = int(windows_id)
                except ValueError:
                    log_audit_entry(
                        "voice_config_error",
                        f"Invalid windows_output_id: {windows_id}, using default",
                        AuditStatus.WARNING,
                    )
                    windows_id = 0
            devices.append(windows_id)

        if get_config_value("voice.use_rvc", False):
            output_id = get_config_value("voice.output_id", 0)
            if isinstance(output_id, str):
                try:
                    output_id = int(output_id)
                except ValueError:
                    log_audit_entry(
                        "voice_config_error",
                        f"Invalid output_id: {output_id}, using default",
                        AuditStatus.WARNING,
                    )
                    output_id = 0
            devices.append(output_id)

        log_audit_entry(
            "voice_devices_list",
            f"Devices used for playback: {devices}",
            AuditStatus.INFO,
        )

        if not devices:
            log_audit_entry(
                "voice_no_devices",
                "[Voice] No output devices configured",
                AuditStatus.WARNING,
            )
            return

        threads: List[threading.Thread] = []
        finished = threading.Event()

        def _play(device_id: int) -> None:
            log_audit_entry(
                "voice_thread_start",
                f"Playback thread started for device: {device_id}",
                AuditStatus.INFO,
            )
            try:
                stream = sd.OutputStream(
                    samplerate=sound.frame_rate,
                    device=device_id,
                    channels=1 if samples.ndim == 1 else samples.shape[1],
                )
                with stream:
                    stream.start()
                    chunk_duration_sec = 0.1
                    chunk_size = int(sound.frame_rate * chunk_duration_sec)
                    idx = 0
                    while idx < len(samples):
                        if cut_voice:
                            log_audit_entry(
                                "voice_playback_interrupted",
                                f"Playback interrupted on device {device_id}",
                                AuditStatus.WARNING,
                            )
                            break
                        end = min(idx + chunk_size, len(samples))
                        stream.write(samples[idx:end])
                        idx = end
                    stream.stop()
            except Exception as exc:
                log_audit_entry(
                    "voice_playback_error",
                    "[Voice] Playback failed",
                    AuditStatus.ERROR,
                    details={"device": device_id, "error": str(exc)},
                )
            finally:
                finished.set()
                log_audit_entry(
                    "voice_thread_finished",
                    f"Playback thread finished for device: {device_id}",
                    AuditStatus.INFO,
                )

        with self._stream_lock:
            self._active_streams.clear()
            for device_id in devices:
                thread = threading.Thread(target=_play, args=(device_id,), daemon=True)
                thread.start()
                threads.append(thread)
                log_audit_entry(
                    "voice_thread_spawned",
                    f"Spawned thread for device: {device_id}",
                    AuditStatus.INFO,
                )

        for thread in threads:
            thread.join()
            log_audit_entry(
                "voice_thread_joined", "Playback thread joined", AuditStatus.INFO
            )

    def stop_all(self) -> None:
        log_audit_entry(
            "voice_stop_all_called", "Attempting to stop all playback", AuditStatus.INFO
        )
        with self._stream_lock:
            sd.stop()
            self._active_streams.clear()
            log_audit_entry(
                "voice_all_streams_stopped",
                "All streams stopped and cleared",
                AuditStatus.INFO,
            )
