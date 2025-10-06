# ==========================================================
# Module: initialize.py
# Purpose: Primary initialization of the LIM project before starting FastAPI.
# Responsible for preparing the environment: creating a config, generating user_id,
# checking directories and basic values.
#
# Used in: main.py
# Features:
# - Separates pre-startup checks from the API startup logic
# - Can be called separately as a setup procedure
# =========================================================
import uuid

from services import config_service
from services import database_service
from services import preset_service
from services import character_service, config_service
from services.logger_service import initialize_log_files, log_audit_entry, AuditStatus
from modules.vision.service import VisionService
from modules.memory.short_term import ensure_short_term_schema, refresh_recent_days
from services.config_service import get_config_value
from utils.structure_utils import get_label_from_file


def run_startup_checks():
    """
    The main method for initializing LIM.
    Runs when main.py starts, before the application starts.
    """

    print("Starting LIM initialization...")
    log_audit_entry(
        event_type="startup_begin",
        msg=f"{get_label_from_file(__file__)} Starting LIM initialization",
        status=AuditStatus.SUCCESS,
    )

    # Checking for availability and creating a config
    config_service.ensure_config_exists()
    preset_service.ensure_presets_exist()

    initialize_log_files()

    # Generate user_id if it is missing
    if not config_service.get_config_value("user_id"):
        user_id = str(uuid.uuid4())
        config_service.set_config_value("user_id", user_id)
        log_audit_entry(
            event_type="user_id_generated",
            msg="[Initialize] Create New user",
            status=AuditStatus.INFO,
            details={},
            meta={"user_id": user_id},
        )

    # Create a database
    database_service.create_database()
    ensure_short_term_schema()

    char_name = config_service.get_config_value("char_name")
    character = None
    if char_name:
        character = character_service.get_or_create_character(char_name)
        refresh_recent_days(character.id)
        log_audit_entry(
            event_type="character_bootstrap",
            msg=f"[Initialize] ensured character '{char_name}' exists",
            status=AuditStatus.SUCCESS,
        )

    # Additional checks may be added here in the future:
    # - presence of directories
    # - presence of char_name
    # - config.json structure

    # Initialize and launch the vision service
    if get_config_value("vision.enabled", False):
        try:
            vision_service = VisionService()
            vision_service.start()
            print("[Initialize] Визуальный сервис запущен")
        except Exception as e:
            print(f"[Initialize] Ошибка запуска визуального сервиса: {e}")

    print("Initialization completed successfully.")
    log_audit_entry(
        event_type="startup_complete",
        msg=f"{get_label_from_file(__file__)} Initialization complete",
        status=AuditStatus.SUCCESS,
    )


def shutdown_services():
    """Shut down all services."""
    # ... other shutdown routines ...

    # Stop the vision service
    try:
        vision_service = VisionService()
        vision_service.stop()
        print("[Initialize] Визуальный сервис остановлен")
    except Exception as e:
        print(f"[Initialize] Ошибка остановки визуального сервиса: {e}")
