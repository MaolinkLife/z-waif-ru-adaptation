import os
import json
import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional

from utils.open_file_w_utf8 import open_utf8
from services.localization_service import get_text, get_active_language

# Paths to logs
LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
TEMP_LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "temp", "logs")

# Create directories if necessary
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(TEMP_LOGS_DIR, exist_ok=True)


def _cleanup_old_log_files(keep_sessions: int = 1) -> None:
    """
    Remove old session logs, keeping only the most recent ones.
    Also resets the rolling debug file.
    """
    try:
        session_logs = [
            file
            for file in os.listdir(LOGS_DIR)
            if file.endswith("_debug.jsonl")
        ]
        session_logs.sort(
            key=lambda name: os.path.getmtime(os.path.join(LOGS_DIR, name)),
            reverse=True,
        )

        for obsolete in session_logs[keep_sessions:]:
            try:
                os.remove(os.path.join(LOGS_DIR, obsolete))
                print(
                    get_text(
                        "logger.cleanup_removed",
                        params={"file": obsolete},
                        default=f"[Logger] Removed old log file: {obsolete}",
                    )
                )
            except OSError as exc:
                print(
                    get_text(
                        "logger.cleanup_remove_failed",
                        params={"file": obsolete, "error": exc},
                        default=f"[Logger] Failed to remove log file {obsolete}: {exc}",
                    )
                )

        rolling_debug = os.path.join(LOGS_DIR, "debug_log.jsonl")
        if os.path.exists(rolling_debug):
            try:
                os.remove(rolling_debug)
                print(
                    get_text(
                        "logger.cleanup_cleared",
                        default="[Logger] Cleared rolling debug log.",
                    )
                )
            except OSError as exc:
                print(
                    get_text(
                        "logger.cleanup_clear_failed",
                        params={"error": exc},
                        default=f"[Logger] Failed to clear rolling debug log: {exc}",
                    )
                )
    except Exception as exc:
        print(
            get_text(
                "logger.cleanup_failed",
                params={"error": exc},
                default=f"[Logger] Log cleanup failed: {exc}",
            )
        )


_cleanup_old_log_files()

# Current session ID
SESSION_ID = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

DEBUG_FILE_PER_SESSION = os.path.join(LOGS_DIR, f"{SESSION_ID}_debug.jsonl")
DEBUG_FILE_CURRENT = os.path.join(LOGS_DIR, "debug_log.jsonl")  # Last active


class AuditStatus(str, Enum):
    SUCCESS = "Success"
    ERROR = "Error"
    WARNING = "Warning"
    INFO = "Info"


@dataclass
class AuditLog:
    event_type: str
    msg: str
    status: AuditStatus = AuditStatus.INFO
    details: dict = field(default_factory=dict)
    meta: Optional[dict] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now().isoformat(timespec="seconds")
    )
    session_id: str = field(default_factory=lambda: SESSION_ID)
    language: str = field(default_factory=get_active_language)
    message_key: Optional[str] = None

    def as_dict(self) -> dict:
        return asdict(self)


def get_session_id():
    return SESSION_ID


def initialize_log_files():
    """
    Initializes empty log files if they do not already exist.
    """
    for path in [DEBUG_FILE_PER_SESSION, DEBUG_FILE_CURRENT]:
        if not os.path.exists(path):
            with open_utf8(path, "w") as file:
                file.write("")


def _write_jsonl(filepath, record):
    with open_utf8(filepath, "a") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def _default_message_key(event_type: Optional[str]) -> Optional[str]:
    if not event_type:
        return None
    return f"logger.{event_type}"


def _resolve_localized_message(
    event_type: str,
    raw_message: Optional[str],
    message_key: Optional[str],
    message_args: Optional[dict],
) -> tuple[str, Optional[str]]:
    params = message_args or {}
    candidate_key = message_key or _default_message_key(event_type)
    default_message = raw_message if isinstance(raw_message, str) else None

    if candidate_key:
        localized = get_text(candidate_key, params=params, default=default_message)
    else:
        localized = default_message or ""

    if not localized and default_message:
        localized = default_message

    return localized, candidate_key


def log_audit_entry(
    event_type: str,
    msg: str,
    status: AuditStatus = AuditStatus.INFO,
    details: Optional[dict] = None,
    meta: Optional[dict] = None,
    *,
    message_key: Optional[str] = None,
    message_args: Optional[dict] = None,
):
    """
    Logging key events to DEBUG_LOG using a strict format.
    """

    localized_message, resolved_key = _resolve_localized_message(
        event_type, msg, message_key, message_args
    )

    meta_payload = dict(meta or {})
    if message_args:
        meta_payload.setdefault("message_args", message_args)

    log = AuditLog(
        event_type=event_type,
        msg=localized_message,
        status=status,
        meta=meta_payload,
        details=details or {},
        timestamp=datetime.now().isoformat(timespec="seconds"),
        session_id=SESSION_ID,
        message_key=resolved_key,
    )
    _write_jsonl(DEBUG_FILE_PER_SESSION, log.as_dict())
    _write_jsonl(DEBUG_FILE_CURRENT, log.as_dict())


def log_error(error_msg, context=None, severity="error"):
    """
    Errors on temp-log and debug.
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    temp_path = os.path.join(TEMP_LOGS_DIR, f"{date_str}_log.txt")

    with open_utf8(temp_path, "a") as file:
        file.write(
            f"[{datetime.now().isoformat(timespec='seconds')}] [SESSION: {SESSION_ID}] ERROR: {error_msg}\n"
        )
        if context:
            file.write(f"Context: {context}\n")

    log_audit_entry(
        event_type="error",
        msg=f"Error occurred: {error_msg}",
        status=AuditStatus.ERROR,
        details={"error": error_msg, "context": context},
        meta={"source": "system", "severity": severity, "context": context or {}},
        message_key="logger.error",
        message_args={"error": error_msg},
    )


def log_debug(message, tag="DEBUG"):
    """
    Console log.
    """
    print(f"[{tag}][{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def get_debug_log():
    """
    Returns the current debug log as a list of entries.
    """
    session_id = get_session_id()
    log_file = os.path.join(LOGS_DIR, f"{session_id}_debug.jsonl")

    if not os.path.exists(log_file):
        return None, session_id

    try:
        with open_utf8(log_file, "r") as file:
            logs = [json.loads(line) for line in file.readlines()]
        return logs, session_id

    except Exception as exc:
        raise RuntimeError(f"Error reading log: {exc}")
