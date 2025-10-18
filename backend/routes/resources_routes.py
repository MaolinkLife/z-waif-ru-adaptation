# routes/resources_routes.py (updated)
import asyncio
import edge_tts
import re
from fastapi import APIRouter
from fastapi.responses import JSONResponse
from services.logger_service import get_debug_log
from services.resource_service import get_audio_resources
from services.monitor_service import (
    get_monitor_screens,
    get_monitor_info,
)  # Add import
from services.config_service import get_config_value

router = APIRouter(prefix="/api/resources", tags=["Resources"])

DEFAULT_VOICE_TIMEOUT = 8  # seconds


def parse_voice_shortname(raw_name: str) -> str:
    # Пример: "Microsoft Server Speech Text to Speech Voice (ru-RU, SvetlanaNeural)"
    match = re.search(r"\(([^,]+),\s*([^)]+)\)", raw_name)
    if match:
        locale = match.group(1)
        shortname = match.group(2)
        return f"{locale}-{shortname}"
    return raw_name


@router.get("/devices")
def get_audio_devices():
    try:
        return get_audio_resources()

    except Exception as e:
        return {
            "status": "error",
            "content": f"Error while getting audio devices: {str(e)}",
        }


# NEW ENDPOINT - Fetch monitor screenshots
@router.get("/monitors/screens")
def get_monitor_screens_endpoint():
    """Return monitors with thumbnails for UI selection."""
    try:
        monitors = get_monitor_screens()
        return {"status": "success", "monitors": monitors}
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error getting monitor screens: {str(e)}",
            "monitors": [],
        }


# Additional endpoint for retrieving monitor information
@router.get("/monitors/info")
def get_monitor_info_endpoint():
    """Return monitor information without thumbnails."""
    try:
        info = get_monitor_info()
        return {"status": "success", "data": info}
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error getting monitor info: {str(e)}",
            "data": {},
        }


@router.get("/voices")
async def get_edge_voices():
    try:
        timeout_raw = get_config_value("voice.voices_timeout_seconds", DEFAULT_VOICE_TIMEOUT)
        try:
            timeout = max(1, int(timeout_raw))
        except (TypeError, ValueError):
            timeout = DEFAULT_VOICE_TIMEOUT

        voices = await asyncio.wait_for(edge_tts.list_voices(), timeout=timeout)
        simplified = [
            {
                "name": parse_voice_shortname(v.get("Name")),
                "gender": v.get("Gender", "Unknown"),
                "styles": v.get("VoicePersonalities", []),
                "categories": v.get("ContentCategories", []),
            }
            for v in voices
        ]
        return {"status": "success", "voices": simplified}
    except asyncio.TimeoutError:
        return {
            "status": "error",
            "message": f"Voice provider timeout after {timeout} seconds.",
            "voices": [],
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Error getting voices: {str(e)}",
            "voices": [],
        }
