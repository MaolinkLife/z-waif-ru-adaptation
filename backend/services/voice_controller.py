import uuid
import os
from datetime import datetime, timezone
from services import stt_service

TEMP_AUDIO_PATH = os.path.join("temp", "voice", "temp_recording.wav")


def start_recording():
    stt_service.start_recording_background(TEMP_AUDIO_PATH)
    return {"status": "ok", "message": "Запись началась."}


def stop_recording_and_process(character_name: str) -> dict:
    """
    Stops recording, saves WAV, decrypts, generates UUID and returns fake message object.
    """
    # First, save the audio
    stt_service.stop_recording_and_save(TEMP_AUDIO_PATH)

    # Now you can safely transcribe
    transcript = stt_service.transcribe_audio(TEMP_AUDIO_PATH)

    message_id = str(uuid.uuid4())
    timestamp = datetime.now(timezone.utc)

    if os.path.exists(TEMP_AUDIO_PATH):
        os.remove(TEMP_AUDIO_PATH)

    return {
        "id": message_id,
        "role": "user",
        "content": transcript,
        "timestamp": timestamp.isoformat(),
    }
