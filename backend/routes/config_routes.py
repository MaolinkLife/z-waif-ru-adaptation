# ===========================================================
# Module: config_routes.py
# Purpose: API endpoints for working with LIM configuration
# Used in: WebUI and any external components that need to read/change config
# Features:
# - Supports full replacement and partial update
# - Returns the entire config via GET request
# ========================================================

from fastapi import APIRouter, Request
from services.character_service import (
    get_character_prompt,
    save_character_prompt,
)
from services.config_service import (
    update_config_bulk,
    save_config,
    apply_preset_by_name,
    get_config,
    get_config_value,
    set_config_value,
)

router = APIRouter(prefix="/api/config", tags=["Config"])


# Returns the entire config
@router.get("/")
def get_full_config():
    return get_config()


# Overwrites the entire config.
@router.post("/")
async def overwrite_config(request: Request):
    new_config = await request.json()
    save_config(new_config)
    return {"status": "ok", "message": "The config has been updated."}


# Updates config
@router.patch("/")
async def update_config_bulk_route(request: Request):
    updates = await request.json()
    updated, failed = update_config_bulk(updates)

    return {
        "status": "partial" if failed else "ok",
        "updated": updated,
        "failed": failed,
    }


# Applies the selected preset
@router.post("/apply_preset")
async def apply_preset(request: Request):
    body = await request.json()
    preset_name = body.get("name")

    if not preset_name:
        return {"status": "error", "message": "Preset name not specified"}

    success = apply_preset_by_name(preset_name)
    if success:
        return {"status": "ok", "message": f"Preset '{preset_name}' applied."}
    else:
        return {"status": "error", "message": "Preset not found"}


@router.get("/system")
def get_system_info():
    char_name = get_config_value("char_name", "default_waifu")
    try:
        prompt = get_character_prompt(char_name)
    except FileNotFoundError:
        prompt = ""

    return {"system": {"char_name": char_name, "prompt": prompt}}


@router.post("/system")
async def update_system_info(request: Request):
    data = await request.json()
    prompt = data.get("prompt")
    char_name = data.get("char_name")  # опционально

    if not prompt:
        return {"status": "error", "message": "prompt is required"}

    # Если char_name не передан — берем из конфига
    if not char_name:
        char_name = get_config_value("char_name", "default_waifu")

    # Обновляем YAML и БД
    save_character_prompt(char_name, prompt)

    # Обновляем char_name в конфиге, если передан
    if data.get("char_name"):
        set_config_value("char_name", char_name)

    return {"status": "ok", "message": f"System prompt for '{char_name}' updated."}
