import sounddevice as sd


def get_output_devices():
    devices = sd.query_devices()
    seen_names = set()
    output_devices = []

    for index, device in enumerate(devices):
        name = device["name"]
        if device["max_output_channels"] > 0 and name not in seen_names:
            output_devices.append((index, name))
            seen_names.add(name)

    return output_devices


def get_device_name_by_id(device_id):
    devices = get_output_devices()
    for idx, name in devices:
        if idx == device_id:
            return f"{name} (ID: {idx})"
    return None


def get_windows_output_candidates():
    virtual_keywords = ["VB", "Cable", "VoiceMeeter", "Virtual", "Voicemod"]
    real_devices = []

    for idx, name in get_output_devices():
        if not any(keyword.lower() in name.lower() for keyword in virtual_keywords):
            real_devices.append((idx, name))

    return real_devices
