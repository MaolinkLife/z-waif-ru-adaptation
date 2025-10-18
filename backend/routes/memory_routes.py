from fastapi import APIRouter, HTTPException

from modules.memory.short_term import (
    ensure_short_term_schema,
    load_recent_records,
    refresh_recent_days,
)
from services import character_service
from services.config_service import get_config_value
from services.logger_service import AuditStatus, log_audit_entry
from services.localization_service import get_text

router = APIRouter(prefix="/api/memory", tags=["Memory"])


@router.post("/refresh")
async def refresh_short_term_memory() -> dict:
    print(
        get_text(
            "memory_routes.refresh_request",
            default="[MemoryRoutes] Запрос на обновление краткосрочной памяти через API.",
        )
    )
    ensure_short_term_schema()

    char_name = get_config_value("system.char_name")
    if not char_name:
        raise HTTPException(status_code=400, detail="Character name not configured")

    character = character_service.get_or_create_character(char_name)
    refresh_recent_days(character.id)
    records = load_recent_records()

    log_audit_entry(
        "memory_route_refresh",
        get_text(
            "memory_routes.refresh_completed",
            default="[MemoryRoutes] Выполнено обновление краткосрочной памяти.",
        ),
        status=AuditStatus.INFO,
        details={"records": len(records)},
        message_key="memory_routes.refresh_completed",
    )
    return {"status": "ok", "records": len(records)}


@router.get("/short-term")
async def list_short_term_memory() -> dict:
    print(
        get_text(
            "memory_routes.list_request",
            default="[MemoryRoutes] Получение записей краткосрочной памяти через API.",
        )
    )
    ensure_short_term_schema()
    records = load_recent_records()
    payload = []
    for record in records:
        payload.append(
            {
                "id": record.id,
                "summary": record.summary,
                "dialogue_ids": record.dialogue_ids,
                "themes": record.themes,
                "created_at": record.created_at.isoformat(),
                "updated_at": record.updated_at.isoformat(),
            }
        )

    log_audit_entry(
        "memory_route_list",
        get_text(
            "memory_routes.list_return",
            default="[MemoryRoutes] Возвращаем список записей краткосрочной памяти.",
        ),
        status=AuditStatus.INFO,
        details={"records": len(payload)},
        message_key="memory_routes.list_return",
    )
    return {"records": payload}
