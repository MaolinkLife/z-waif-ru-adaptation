from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from services.preset_service import (
    get_all_presets, 
    get_preset_by_name, 
    update_or_add_preset, 
    apply_preset_to_config
)

router = APIRouter(prefix="/api/presets", tags=["Presets"])


# Get a list of all presets
@router.get("/")
def get_presets():
    try:
        presets = get_all_presets()
        return {"status": "ok", "presets": presets}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


# Get preset by name
@router.get("/{name}")
def get_preset(name: str):
    preset = get_preset_by_name(name)
    if preset:
        return {"status": "ok", "preset": preset}
    return JSONResponse(status_code=404, content={"status": "error", "message": "Preset not found"})


# Add or update preset
@router.post("/")
async def save_preset(request: Request):
    try:
        preset = await request.json()
        if not preset.get("name"):
            return JSONResponse(status_code=400, content={"status": "error", "message": "Preset name is required"})

        update_or_add_preset(preset)
        return {"status": "ok", "message": "Preset saved"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


@router.post("/apply")
async def apply_existing_preset(request: Request):
    try:
        data = await request.json()
        preset_name = data.get("name")

        if not preset_name:
            return JSONResponse(status_code=400, content={"status": "error", "message": "Preset name is required."})

        preset = get_preset_by_name(preset_name)
        if not preset:
            return JSONResponse(status_code=404, content={"status": "error", "message": "Preset not found."})

        apply_preset_to_config(preset)

        return JSONResponse(content={"status": "ok", "message": f"Preset '{preset_name}' applied to config."})

    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})