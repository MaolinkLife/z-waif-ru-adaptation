from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from services.storage_service import get_media_entry, resolve_media_path

router = APIRouter(prefix="/api/media", tags=["Media"])


@router.get("/{media_id}")
def download_media(media_id: str):
    entry = get_media_entry(media_id)
    file_path = resolve_media_path(entry)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    return FileResponse(
        path=file_path,
        media_type=entry.mime_type,
        filename=entry.file_name,
    )
