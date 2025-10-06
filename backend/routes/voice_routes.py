import json
import asyncio
from fastapi import APIRouter, Body

from modules.tts.service import force_cut_voice
from services.api_service import play_message, run_standard
from services import config_service, voice_controller
from modules.voice.vad_listener import (
    start_vad_background,
    stop_vad,
    is_vad_running,
)

from core.websocket_manager import manager

router = APIRouter(prefix="/api/voice", tags=["Voice"])

@router.post("/stop")
async def stop_voice():
    force_cut_voice()
    return {"status": "ok", "message": "Playback has stopped"}


@router.post("/play")
def play_message_by_id(request: dict = Body(...)):
    message_id = request.get("message_id")
    if not message_id:
        return {"status": "error", "message": "message_id не указан"}
    
    play_message(message_id)
    return {"status": "ok", "message": f"Playing the message: {message_id}"}


@router.post("/record/start")
def start_record():
    return voice_controller.start_recording()


@router.post("/record/stop")
async def stop_record():
    char_name = config_service.get_config_value("char_name", "default_waifu")
    data = voice_controller.stop_recording_and_process(char_name)
    
    async def push_ws(msg):
        await manager.send_message(json.dumps(msg, ensure_ascii=False))
    
    await run_standard([data], emit_ws_fn=push_ws)

    return {
        "status": "ok",
        "data": data
    }


# --- VoiceMode (VAD) controls ---
@router.post("/mode/start")
async def start_voice_mode():
    """Запустить VoiceMode (постоянное прослушивание)"""
    started, message = await start_vad_background()
    status = "ok" if started else "error"
    return {"status": status, "message": message, "running": is_vad_running()}


@router.post("/mode/stop")
async def stop_voice_mode():
    """Остановить VoiceMode (без принудительного завершения записи)"""
    stopped, message = await stop_vad(wait=True)
    status = "ok" if stopped else "error"
    return {"status": status, "message": message, "running": is_vad_running()}


@router.get("/mode/status")
async def voice_mode_status():
    return {"status": "ok", "running": is_vad_running()}
