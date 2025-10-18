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
from services.localization_service import get_text

cut_voice = False


class AudioPlayback:
    def __init__(self) -> None:
        self._active_streams: List[sd.OutputStream] = []
        self._stream_lock = threading.Lock()

    def play_file(self, file_path: str, interrupt_event=None) -> None:
        global cut_voice
        cut_voice = False
        message_start = get_text(
            "logger.voice_play_start",
            params={"file_path": file_path},
            default=f"[Audio Playback] Starting playback for: {file_path}",
        )
        print(message_start)
        log_audit_entry(
            "voice_play_start",
            message_start,
            AuditStatus.INFO,
            message_key="logger.voice_play_start",
            message_args={"file_path": file_path},
        )

        if not os.path.isfile(file_path):
            message_missing = get_text(
                "logger.voice_audio_missing",
                params={"file_path": file_path},
                default=f"[Audio Playback] File not found: {file_path}",
            )
            print(message_missing)
            log_audit_entry(
                "voice_audio_missing",
                message_missing,
                AuditStatus.WARNING,
                message_key="logger.voice_audio_missing",
                message_args={"file_path": file_path},
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
                    message_config_error = get_text(
                        "logger.voice_config_error",
                        params={"config_key": "windows_output_id", "value": windows_id},
                        default=f"[Audio Playback] Invalid windows_output_id: {windows_id}, using default",
                    )
                    print(message_config_error)
                    log_audit_entry(
                        "voice_config_error",
                        message_config_error,
                        AuditStatus.WARNING,
                        message_key="logger.voice_config_error",
                        message_args={"config_key": "windows_output_id", "value": windows_id},
                    )
                    windows_id = 0
            devices.append(windows_id)

        if get_config_value("voice.use_rvc", False):
            output_id = get_config_value("voice.output_id", 0)
            if isinstance(output_id, str):
                try:
                    output_id = int(output_id)
                except ValueError:
                    message_config_error = get_text(
                        "logger.voice_config_error",
                        params={"config_key": "output_id", "value": output_id},
                        default=f"[Audio Playback] Invalid output_id: {output_id}, using default",
                    )
                    print(message_config_error)
                    log_audit_entry(
                        "voice_config_error",
                        message_config_error,
                        AuditStatus.WARNING,
                        message_key="logger.voice_config_error",
                        message_args={"config_key": "output_id", "value": output_id},
                    )
                    output_id = 0
            devices.append(output_id)

        formatted_devices = ""
        for i, device in enumerate(devices):
            if i > 0:
                formatted_devices += ", "
            formatted_devices += str(device)

        message_devices = get_text(
            "logger.voice_devices_list",
            params={"devices": formatted_devices},
            default=f"[Audio Playback] Devices used for playback: {formatted_devices}",
        )
        print(message_devices)
        log_audit_entry(
            "voice_devices_list",
            message_devices,
            AuditStatus.INFO,
            message_key="logger.voice_devices_list",
            message_args={"devices": formatted_devices},
        )

        if not devices:
            message_no_devices = get_text(
                "logger.voice_no_devices",
                default="[Audio Playback] No output devices configured",
            )
            print(message_no_devices)
            log_audit_entry(
                "voice_no_devices",
                message_no_devices,
                AuditStatus.WARNING,
                message_key="logger.voice_no_devices",
            )
            return

        threads: List[threading.Thread] = []
        finished = threading.Event()

        def _play(device_id: int) -> None:
            message_thread_start = get_text(
                "logger.voice_thread_start",
                params={"device_id": device_id},
                default=f"[Audio Playback] Playback thread started for device: {device_id}",
            )
            print(message_thread_start)
            log_audit_entry(
                "voice_thread_start",
                message_thread_start,
                AuditStatus.INFO,
                message_key="logger.voice_thread_start",
                message_args={"device_id": device_id},
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
                            message_interrupted = get_text(
                                "logger.voice_playback_interrupted",
                                params={"device_id": device_id},
                                default=f"[Audio Playback] Playback interrupted on device {device_id}",
                            )
                            print(message_interrupted)
                            log_audit_entry(
                                "voice_playback_interrupted",
                                message_interrupted,
                                AuditStatus.WARNING,
                                message_key="logger.voice_playback_interrupted",
                                message_args={"device_id": device_id},
                            )
                            break
                        end = min(idx + chunk_size, len(samples))
                        stream.write(samples[idx:end])
                        idx = end
                    stream.stop()
            except Exception as exc:
                message_playback_error = get_text(
                    "logger.voice_playback_error",
                    default="[Audio Playback] Playback failed",
                )
                print(
                    f"{message_playback_error} (device={device_id}, error={exc})"
                )
                log_audit_entry(
                    "voice_playback_error",
                    message_playback_error,
                    AuditStatus.ERROR,
                    details={"device": device_id, "error": str(exc)},
                    message_key="logger.voice_playback_error",
                    message_args={"device_id": device_id},
                )
            finally:
                finished.set()
                message_thread_finished = get_text(
                    "logger.voice_thread_finished",
                    params={"device_id": device_id},
                    default=f"[Audio Playback] Playback thread finished for device: {device_id}",
                )
                print(message_thread_finished)
                log_audit_entry(
                    "voice_thread_finished",
                    message_thread_finished,
                    AuditStatus.INFO,
                    message_key="logger.voice_thread_finished",
                    message_args={"device_id": device_id},
                )

        with self._stream_lock:
            self._active_streams.clear()
            for device_id in devices:
                thread = threading.Thread(target=_play, args=(device_id,), daemon=True)
                thread.start()
                threads.append(thread)
                message_thread_spawned = get_text(
                    "logger.voice_thread_spawned",
                    params={"device_id": device_id},
                    default=f"[Audio Playback] Spawned thread for device: {device_id}",
                )
                print(message_thread_spawned)
                log_audit_entry(
                    "voice_thread_spawned",
                    message_thread_spawned,
                    AuditStatus.INFO,
                    message_key="logger.voice_thread_spawned",
                    message_args={"device_id": device_id},
                )

        for thread in threads:
            thread.join()
            message_thread_joined = get_text(
                "logger.voice_thread_joined",
                default="[Audio Playback] Playback thread joined",
            )
            print(message_thread_joined)
            log_audit_entry(
                "voice_thread_joined",
                message_thread_joined,
                AuditStatus.INFO,
                message_key="logger.voice_thread_joined",
            )

    def stop_all(self) -> None:
        message_stop_all = get_text(
            "logger.voice_stop_all_called",
            default="[Audio Playback] Attempting to stop all playback",
        )
        print(message_stop_all)
        log_audit_entry(
            "voice_stop_all_called",
            message_stop_all,
            AuditStatus.INFO,
            message_key="logger.voice_stop_all_called",
        )
        with self._stream_lock:
            sd.stop()
            self._active_streams.clear()
            message_all_stopped = get_text(
                "logger.voice_all_streams_stopped",
                default="[Audio Playback] All streams stopped and cleared",
            )
            print(message_all_stopped)
            log_audit_entry(
                "voice_all_streams_stopped",
                message_all_stopped,
                AuditStatus.INFO,
                message_key="logger.voice_all_streams_stopped",
            )
