import os
import json
import uuid
from datetime import datetime
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Literal, Optional

from utils.open_file_w_utf8 import open_utf8

# Current session ID
SESSION_ID = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"

# Paths to logs
LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")
TEMP_LOGS_DIR = os.path.join(os.path.dirname(__file__), "..", "temp", "logs")
DEBUG_FILE_PER_SESSION = os.path.join(LOGS_DIR, f"{SESSION_ID}_debug.jsonl")
DEBUG_FILE_CURRENT = os.path.join(LOGS_DIR, "debug_log.jsonl")  # Last active

# Create directories if necessary
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(TEMP_LOGS_DIR, exist_ok=True)


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
            with open_utf8(path, "w") as f:
                pass  # just create an empty file


def _write_jsonl(filepath, record):
    with open_utf8(filepath, "a") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_error(error_msg, context=None, severity="error"):
    """
    Errors on temp-log and debug
    """
    date_str = datetime.now().strftime("%Y-%m-%d")
    temp_path = os.path.join(TEMP_LOGS_DIR, f"{date_str}_log.txt")

    with open_utf8(temp_path, "a") as f:
        f.write(
            f"[{datetime.now().isoformat(timespec='seconds')}] [SESSION: {SESSION_ID}] ERROR: {error_msg}\n"
        )
        if context:
            f.write(f"Context: {context}\n")

    log_audit_entry(
        event_type="error",
        msg=f"Error occurred: {error_msg}",
        status=AuditStatus.ERROR,
        details={"error": error_msg, "context": context},
        meta={"source": "system", "severity": severity, "context": context or {}},
    )


def log_audit_entry(
    event_type: str,
    msg: str,
    status: AuditStatus = AuditStatus.INFO,
    details: dict = None,
    meta: dict = None,
):
    """
    Logging key events to DEBUG_LOG using a strict format
    """

    log = AuditLog(
        event_type=event_type,
        msg=msg,
        status=status,
        meta=meta or {},
        details=details or {},
        timestamp=datetime.now().isoformat(timespec="seconds"),
        session_id=SESSION_ID,
    )
    _write_jsonl(DEBUG_FILE_PER_SESSION, log.as_dict())
    _write_jsonl(DEBUG_FILE_CURRENT, log.as_dict())


def log_debug(message, tag="DEBUG"):
    """
    Console log
    """
    print(f"[{tag}][{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")


def get_debug_log():
    """
    Returns the current debug log as a list of entries
    """
    session_id = get_session_id()
    log_file = os.path.join(LOGS_DIR, f"{session_id}_debug.jsonl")

    if not os.path.exists(log_file):
        return None, session_id

    try:
        with open_utf8(log_file, "r") as f:
            logs = [json.loads(line) for line in f.readlines()]
        return logs, session_id

    except Exception as e:
        raise RuntimeError(f"Error reading log: {e}")
