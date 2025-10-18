# ===========================================================
# Module: ollama_routes.py
# Purpose: Endpoints for interacting with the Ollama model and getting history
# Used in: WebUI or other clients sending requests to LLM
# Features:
# - Delegates message preparation to api_service and transport to ollama client utils
# - Has endpoints for getting the list of models and history
# ========================================================

from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from modules.generative import conversation
from core.decision_layer import decision_layer
from modules.ollama import client as ollama_client

# from services.history_service import get_history
from services import config_service, database_service
from services.logger_service import log_audit_entry, AuditStatus

router = APIRouter(prefix="/api/ollama", tags=["Ollama"])


# Sending messages to Ollama (chat request)
@router.post("/chat")
async def chat(payload: dict):
    history = payload.get("history", [])
    last_user = next(
        (msg for msg in reversed(history) if msg.get("role") == "user"), None
    )
    if not last_user:
        return {"status": "error", "message": "No user message provided"}

    user_input = dict(last_user)
    user_input.setdefault("history", history[:-1])

    decision_context = await decision_layer.process_message(user_input, None)
    decision_context.pop("raw_media", None)
    response = await conversation.generate_standard(
        decision_context,
        history,
        user_input,
    )
    return {"response": response}


# Returns a list of available Ollama models.
@router.get("/models")
async def get_available_models():
    return ollama_client.list_models()


@router.get("/history")
async def fetch_history(limit: int = 32):
    try:
        char_name = config_service.get_config_value("system.char_name", "default_waifu")
        history = database_service.get_history(char_name, limit)
        return JSONResponse(content={"status": "ok", "history": history})
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"status": "error", "message": str(e)}
        )


@router.delete("/history/message")
async def delete_message_api(message_id: str, chain: bool = False):
    try:
        if chain:
            return database_service.delete_message_chain(message_id)
        else:
            return database_service.delete_message(message_id)
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"status": "error", "message": str(e)}
        )


@router.post("/history/reroll")
async def reroll_assistant_message(payload: dict):
    try:
        message_id = payload.get("message_id")
        if not message_id:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "message": "message_id is required"},
            )

        new_reply = database_service.reroll_message(message_id)
        return JSONResponse(content={"status": "ok", "new_message": new_reply})

    except Exception as e:
        log_audit_entry(
            event_type="reroll_request_error",
            msg="[Ollama Router]: Error while executing rerolll",
            status=AuditStatus.ERROR,
            details={"input": payload, "error": str(e)},
        )
        return JSONResponse(
            status_code=500, content={"status": "error", "message": str(e)}
        )
