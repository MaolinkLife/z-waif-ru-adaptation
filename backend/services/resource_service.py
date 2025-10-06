# services/resource_service.py (updated)
from utils.audio_devices import (
    get_output_devices,
    get_windows_output_candidates,
    get_device_name_by_id,
    get_input_devices,  # Add import
)


def get_audio_resources():
    """Retrieve all audio resources."""
    try:
        return {
            "status": "success",
            "all_devices": get_output_devices(),
            "get_windows_output": get_windows_output_candidates(),
            "recording_devices": get_input_devices(),  # Include recording devices
            "message": "Audio resources retrieved successfully",
        }
    except Exception as e:
        return {
            "status": "error",
            "content": f"Error while getting audio resources: {str(e)}",
            "all_devices": [],
            "get_windows_output": [],
            "recording_devices": [],
        }


def get_audio_device_name(device_id):
    """Return an audio device name by its ID."""
    return get_device_name_by_id(device_id)
