"""Facade helpers for TTS operations, replacing legacy voice_service."""

from __future__ import annotations

from modules.tts import TTSManager, TTSRequest
from modules.tts.state import voice_state

_tts_manager = TTSManager()


def speak_line(text: str, refuse_pause: bool = False) -> bool:
    if not text:
        return False
    _tts_manager.enqueue(text, refuse_pause=refuse_pause)
    return True


def generate_tts(text: str, filename: str):
    return _tts_manager.synthesize_to_file(TTSRequest(text=text), filename)


def play_voice_output(file_path: str) -> None:
    _tts_manager.play_file(file_path)


def stream_speak_line(text: str, devices: list[int]):
    result = speak_line(text)
    return result


def check_if_speaking() -> bool:
    return voice_state.stage().value == "speaking"


def set_speaking(flag: bool) -> None:
    if flag:
        voice_state.enter_speaking("tts_active")
    else:
        voice_state.enter_listening("tts_idle")


def force_cut_voice() -> None:
    _tts_manager.stop()


def log_last_output(text: str) -> None:
    _tts_manager.log_output(text)


def is_self_trigger(text: str) -> bool:
    return _tts_manager.matches_recent_output(text)


def shutdown() -> None:
    _tts_manager.shutdown()
