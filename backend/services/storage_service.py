import base64
import os
import re
import uuid
import mimetypes
import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional

from fastapi import HTTPException

from constants.paths import STORAGE_DIR
from models.models import Storage
from services.db_core import SessionLocal, DB_PATH
from services.logger_service import log_audit_entry, AuditStatus

DEFAULT_MIME_TYPE = "application/octet-stream"

CATEGORY_DIRECTORIES = {
    "image": "images",
    "audio": "audio",
    "video": "video",
    "document": "documents",
    "other": "other",
}

FILES_ROOT = Path(STORAGE_DIR) / "files"


_schema_checked = False


def _ensure_schema() -> None:
    global _schema_checked
    if _schema_checked:
        return
    conn = None
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.execute("PRAGMA table_info(storage)")
        columns = [row[1] for row in cursor.fetchall()]
        if "description" not in columns:
            conn.execute("ALTER TABLE storage ADD COLUMN description TEXT")
            conn.commit()
            log_audit_entry(
                "storage_schema_upgrade",
                "[StorageService] Added description column to storage table.",
                AuditStatus.INFO,
            )
    except Exception as exc:
        log_audit_entry(
            "storage_schema_upgrade_error",
            "[StorageService] Failed to ensure storage schema.",
            AuditStatus.ERROR,
            details={"error": str(exc)},
        )
    finally:
        if conn:
            conn.close()
        _schema_checked = True


def _ensure_directories() -> None:
    for folder in CATEGORY_DIRECTORIES.values():
        path = FILES_ROOT / folder
        path.mkdir(parents=True, exist_ok=True)


_ensure_schema()
_ensure_directories()


def _safe_filename(name: str) -> str:
    name = os.path.basename(name or "file")
    name = re.sub(r"[^a-zA-Z0-9_.-]", "_", name)
    return name or "file"


def _pick_extension(file_name: str, mime_type: str) -> str:
    base_name, ext = os.path.splitext(file_name)
    if ext:
        return ext
    guessed = mimetypes.guess_extension(mime_type or "")
    if guessed:
        return guessed
    return ".bin"


def _category_to_folder(category: str) -> str:
    return CATEGORY_DIRECTORIES.get(category, CATEGORY_DIRECTORIES["other"])


def save_media_for_message(
    message_id: str,
    media_items: Optional[Iterable[dict]],
    session=None,
) -> List[Storage]:
    if not media_items:
        return []

    own_session = False
    if session is None:
        session = SessionLocal()
        own_session = True

    saved_entries: List[Storage] = []

    try:
        media_list = list(media_items)

        log_audit_entry(
            "storage_save_start",
            "[StorageService] Saving media attachments.",
            AuditStatus.INFO,
            details={"message_id": message_id, "count": len(media_list)},
        )

        for item in media_list:
            if not isinstance(item, dict):
                log_audit_entry(
                    "storage_item_invalid",
                    "[StorageService] Media item is not a dict.",
                    AuditStatus.WARNING,
                    details={"message_id": message_id},
                )
                continue

            data = item.get("data")
            if not data:
                log_audit_entry(
                    "storage_item_empty",
                    "[StorageService] Media item has no data.",
                    AuditStatus.WARNING,
                    details={"message_id": message_id, "name": item.get("name")},
                )
                continue

            mime_type = item.get("mimeType") or DEFAULT_MIME_TYPE
            category = (item.get("category") or "other").lower()
            original_name = _safe_filename(item.get("name") or "file")

            log_audit_entry(
                "storage_item_processing",
                "[StorageService] Processing media item.",
                AuditStatus.INFO,
                details={
                    "message_id": message_id,
                    "name": original_name,
                    "mime_type": mime_type,
                    "category": category,
                },
            )
            extension = _pick_extension(original_name, mime_type)
            unique_name = f"{uuid.uuid4().hex}{extension}"
            target_folder = FILES_ROOT / _category_to_folder(category)
            target_folder.mkdir(parents=True, exist_ok=True)
            full_path = target_folder / unique_name

            try:
                file_bytes = base64.b64decode(data, validate=False)
            except Exception as decode_error:
                log_audit_entry(
                    "storage_decode_failed",
                    "[StorageService] Failed to decode media payload.",
                    AuditStatus.ERROR,
                    details={"error": str(decode_error), "name": original_name},
                )
                continue

            try:
                full_path.write_bytes(file_bytes)
            except Exception as write_error:
                log_audit_entry(
                    "storage_write_failed",
                    "[StorageService] Failed to write media file.",
                    AuditStatus.ERROR,
                    details={"error": str(write_error), "path": str(full_path)},
                )
                continue

            relative_path = full_path.relative_to(Path(STORAGE_DIR))

            entry = Storage(
                id=item.get("id") or str(uuid.uuid4()),
                message_id=message_id,
                file_name=original_name,
                file_path=str(relative_path).replace("\\", "/"),
                mime_type=mime_type,
                size=len(file_bytes),
                category=category,
                description=item.get("description"),
            )
            session.add(entry)
            saved_entries.append(entry)

            log_audit_entry(
                "storage_item_saved",
                "[StorageService] Media item saved.",
                AuditStatus.SUCCESS,
                details={
                    "message_id": message_id,
                    "storage_id": entry.id,
                    "path": str(relative_path),
                },
            )

        if saved_entries:
            session.commit()
            for entry in saved_entries:
                session.refresh(entry)

            log_audit_entry(
                "storage_batch_saved",
                "[StorageService] Stored media batch.",
                AuditStatus.SUCCESS,
                details={
                    "message_id": message_id,
                    "saved_count": len(saved_entries),
                },
            )
        else:
            log_audit_entry(
                "storage_batch_empty",
                "[StorageService] No media saved for message.",
                AuditStatus.INFO,
                details={"message_id": message_id},
            )

        return saved_entries
    finally:
        if own_session:
            session.close()


def delete_media_files(entries: Iterable[Storage]) -> None:
    for entry in list(entries or []):
        try:
            full_path = resolve_media_path(entry)
            if full_path.exists():
                full_path.unlink()
                log_audit_entry(
                    "storage_item_deleted",
                    "[StorageService] Media file deleted.",
                    AuditStatus.SUCCESS,
                    details={"storage_id": entry.id, "path": str(full_path)},
                )
            else:
                log_audit_entry(
                    "storage_item_missing",
                    "[StorageService] Media file not found during deletion.",
                    AuditStatus.WARNING,
                    details={"storage_id": entry.id, "path": str(full_path)},
                )
        except Exception as exc:
            log_audit_entry(
                "storage_item_delete_error",
                "[StorageService] Failed to delete media file.",
                AuditStatus.ERROR,
                details={"storage_id": entry.id, "error": str(exc)},
            )


def serialize_media_entries(entries: Iterable[Storage]) -> List[dict]:
    serialized = []
    for entry in entries or []:
        serialized.append(
            {
                "id": entry.id,
                "name": entry.file_name,
                "mimeType": entry.mime_type,
                "size": entry.size,
                "category": entry.category,
                "description": entry.description,
                "url": f"/api/media/{entry.id}",
            }
        )
    return serialized


def get_media_entry(media_id: str) -> Storage:
    session = SessionLocal()
    try:
        entry = session.query(Storage).filter_by(id=media_id).first()
        if not entry:
            raise HTTPException(status_code=404, detail="File not found")
        session.expunge(entry)
        return entry
    finally:
        session.close()


def resolve_media_path(entry: Storage) -> Path:
    full_path = Path(STORAGE_DIR) / entry.file_path
    return full_path
