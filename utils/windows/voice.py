import time
import os
import asyncio
import uuid
import numpy as np

from pydub import AudioSegment
from utils.config_manager import get_config_value

import sounddevice as sd
import edge_tts

import utils.hotkeys
import utils.voice_splitter
import utils.zw_logging
import utils.settings

assert os.name == "nt"  # type: ignore

# ——— Settings ——— #
# VB_CABLE_OUTPUT_ID = 26
is_speaking = False
cut_voice = False

# ——— Main Functions ——— #
async def generate_tts(text, filename):
    voice = get_config_value("voice.voice_language", "ru-RU-SvetlanaNeural") # Voice to play
    communicate = edge_tts.Communicate(text, voice=voice)
    await communicate.save(filename)


def play_voice_output(file_path):
    windows_output = get_config_value("voice.windows_output_id", 0) # Standart Windows Output ID
    virtual_output = get_config_value("voice.output_id", 0) # VBCable or VoiceMeeter Output ID
    
    sound = AudioSegment.from_file(file_path)
    samples = np.array(sound.get_array_of_samples()).astype(np.float32)
    samples /= np.iinfo(sound.array_type).max
    
    device_id = virtual_output if utils.settings.use_rvc_output else windows_output
    utils.zw_logging.update_debug_log(f"🎧 Using device ID: {device_id}")
    
    sd.play(samples, samplerate=sound.frame_rate, device=device_id)
    sd.wait()


def speak_line(s_message, refuse_pause):
    global cut_voice
    cut_voice = False

    chunky_message = utils.voice_splitter.split_into_sentences(s_message)

    for chunk in chunky_message:
        try:
            filename = f"tts_output_{uuid.uuid4()}.mp3"
            asyncio.run(generate_tts(chunk, filename))
            play_voice_output(filename)
            os.remove(filename) # Deletes the file after listening

            time.sleep(0.05 if not refuse_pause else 0.001)

            if utils.hotkeys.NEXT_PRESSED or utils.hotkeys.REDO_PRESSED or cut_voice:
                cut_voice = False
                break

        except Exception as e:
            utils.zw_logging.update_debug_log(f"Error with voice! {str(e)}")

    utils.hotkeys.cooldown_listener_timer()
    set_speaking(False)
    return


# ——— STATUS FLAGS ——— #
def check_if_speaking() -> bool:
    return is_speaking


def set_speaking(set: bool):
    global is_speaking
    is_speaking = set


def force_cut_voice():
    global cut_voice
    cut_voice = True
