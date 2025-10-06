# utils/audio_utils.py (updated)
import sounddevice as sd


def get_input_devices():
    """Return a list of recording (input) devices."""
    devices = sd.query_devices()
    input_devices = []

    for index, device in enumerate(devices):
        name = device["name"]
        if device["max_input_channels"] > 0:
            input_devices.append((index, name))

    return input_devices


def get_output_devices():
    """Return a list of playback (output) devices."""
    devices = sd.query_devices()
    output_devices = []

    for index, device in enumerate(devices):
        name = device["name"]
        if device["max_output_channels"] > 0:
            output_devices.append((index, name))

    return output_devices


def get_device_name_by_id(device_id, device_type="input"):
    """Return a device name by its ID."""
    if device_type == "input":
        devices = get_input_devices()
    else:
        devices = get_output_devices()

    for idx, name in devices:
        if idx == device_id:
            return f"{name} (ID: {idx})"
    return None


def get_windows_output_candidates():
    """Return a list of non-virtual output devices."""
    virtual_keywords = ["VB", "Cable", "VoiceMeeter", "Virtual", "Voicemod"]
    real_devices = []

    for idx, name in get_output_devices():
        lowered = name.lower()
        if not any(keyword.lower() in lowered for keyword in virtual_keywords):
            real_devices.append((idx, name))

    return real_devices


def get_all_audio_devices():
    """Return aggregated info for all available audio devices."""
    try:
        input_devices = get_input_devices()
        output_devices = get_output_devices()
        windows_output = get_windows_output_candidates()

        return {
            "input_devices": input_devices,
            "output_devices": output_devices,
            "windows_output": windows_output,
        }
    except Exception as e:
        return {
            "input_devices": [],
            "output_devices": [],
            "windows_output": [],
            "error": str(e),
        }
