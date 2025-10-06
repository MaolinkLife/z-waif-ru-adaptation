import sounddevice as sd
import numpy as np
import tempfile
import os
import wave
from faster_whisper import WhisperModel
from services.config_service import get_config_value

# =================================
# STATUS VARIABLES
# ================================
_stream = None
_buffer = []
_is_recording = False

# =================================
# CONSTANTS
# ================================
SAMPLE_RATE = 16000
CHANNELS = 1
MODEL = WhisperModel("base", device="cpu", compute_type="int8")


# =================================
# SYNCHRONOUS RECORDING
# ================================
def record_audio(filename: str, duration: int = 5):
    print(f"[🎙] Recording for {duration} seconds...")
    audio = sd.rec(
        int(duration * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
    )
    sd.wait()

    _save_wave(filename, audio)
    print(f"[Record] Saved audio to: {filename}")


# ==============================================
# TRANSCRIPTION
# ==============================================
def transcribe_audio(filename: str) -> str:
    stt_lang = get_config_value("stt.language", None)
    auto_detect = get_config_value("stt.auto_detect", True)

    if auto_detect or not stt_lang:
        segments, _ = MODEL.transcribe(filename)
    else:
        lang_code = stt_lang.split("-")[0]  # "ru-RU" → "ru"
        segments, _ = MODEL.transcribe(filename, language=lang_code)

    result = " ".join(segment.text for segment in segments)
    return result


# =================================
# RECORDING + TRANSCRIPTION
# =================================
def record_and_transcribe() -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        path = tmp.name
    record_audio(path)
    result = transcribe_audio(path)
    os.remove(path)
    return result


# ================================
# BACKGROUND RECORDING
# ================================
def start_recording_background(filename: str):
    global _stream, _buffer, _is_recording

    if _is_recording:
        print("[Record] Recording is already in progress.")
        return

    os.makedirs(os.path.dirname(filename), exist_ok=True)

    _buffer = []
    _is_recording = True

    def callback(indata, frames, time, status):
        if status:
            print(f"[Record] Record status: {status}")
        if _is_recording:
            _buffer.append(indata.copy())

    _stream = sd.InputStream(
        samplerate=SAMPLE_RATE, channels=CHANNELS, dtype="int16", callback=callback
    )
    _stream.start()
    print("[Record] Background recording has started...")


# ================================
# STOP + SAVE WAV
# ================================
def stop_recording_and_save(filename: str):
    global _stream, _is_recording, _buffer

    if not _is_recording:
        raise RuntimeError("Recording is not active - stopping is not possible.")

    _is_recording = False

    if _stream:
        _stream.stop()
        _stream.close()
        _stream = None

    if not _buffer:
        raise RuntimeError("The buffer is empty. Nothing written.")

    audio = np.concatenate(_buffer, axis=0)
    _save_wave(filename, audio)
    _buffer.clear()

    print(f"[Record] Audio saved: {filename}")


# =================================
# WAV SAVE UTILITY
# ================================
def _save_wave(filename: str, audio: np.ndarray):
    with wave.open(filename, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # int16 → 2 bytes
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())


# ================================
# FLAG: IS RECORDING IN PROGRESS
# =================================
def is_recording() -> bool:
    return _is_recording


# ================================
# DEBUG: STATUS
# ================================
def get_recording_state():
    return {
        "recording": _is_recording,
        "stream": _stream is not None,
        "buffer_size": len(_buffer),
    }
