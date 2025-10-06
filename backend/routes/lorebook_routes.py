# api/lorebook_routes.py
# ==========================================================
# Module: lorebook_routes.py
# Purpose: FastAPI endpoints for Lorebook management
# Used: by WebUI for knowledge base management
# ==========================================================

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from modules.memory import lorebook

router = APIRouter(prefix="/api/lorebook", tags=["Lorebook"])


@router.get("/", response_model=List[Dict[str, Any]])
def get_all_entries():
    """Получить все записи из Lorebook"""
    return lorebook.get_entries()


@router.post("/", response_model=Dict[str, Any])
def create_entry(entry: Dict[str, Any]):
    """Создать новую запись в Lorebook"""
    created = lorebook.add_entry(entry)
    if created:
        return {"status": "success", "entry": created}

    raise HTTPException(status_code=500, detail="Failed to create entry")


@router.put("/{entry_id}", response_model=Dict[str, Any])
def update_entry(entry_id: int, entry: Dict[str, Any]):
    """Обновить запись в Lorebook"""
    updated = lorebook.update_entry(entry_id, entry)
    if updated:
        return {"status": "success", "entry": updated}

    raise HTTPException(status_code=404, detail="Entry not found")


@router.delete("/{entry_id}")
def delete_entry(entry_id: int):
    """Удалить запись из Lorebook"""
    if lorebook.delete_entry(entry_id):
        return {"status": "success", "message": "Entry deleted"}
    else:
        raise HTTPException(status_code=404, detail="Entry not found")


@router.get("/search")
def search_entries(query: str = ""):
    """Поиск записей по ключевым словам"""
    return lorebook.search_entries(query=query, use_keyword_fallback=True)
