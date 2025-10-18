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
from services.localization_service import get_text
from modules.vision.service import VisionService
from modules.memory.short_term import ensure_short_term_schema, refresh_recent_days
from services.config_service import get_config_value
from utils.structure_utils import get_label_from_file


def run_startup_checks():
    """
    The main method for initializing LIM.
    Runs when main.py starts, before the application starts.
    """

    label = get_label_from_file(__file__)
    print(
        get_text(
            "initialize.print_start",
            params={"label": label},
            default="Starting LIM initialization...",
        )
    )
    log_audit_entry(
        event_type="startup_begin",
        msg=get_text(
            "initialize.startup_begin",
            params={"label": label},
            default=f"{label} Starting LIM initialization",
        ),
        status=AuditStatus.SUCCESS,
        message_key="initialize.startup_begin",
        message_args={"label": label},
    )

    # Checking for availability and creating a config
    config_service.ensure_config_exists()
    preset_service.ensure_presets_exist()

    initialize_log_files()

    # Generate user_id if it is missing
    if not config_service.get_config_value("system.user_id"):
        user_id = str(uuid.uuid4())
        config_service.set_config_value("system.user_id", user_id)
        log_audit_entry(
            event_type="user_id_generated",
            msg=get_text(
                "initialize.user_id_created",
                default="[Initialize] Create New user",
            ),
            status=AuditStatus.INFO,
            details={},
            meta={"user_id": user_id},
            message_key="initialize.user_id_created",
        )

    # Create a database
    database_service.create_database()
    ensure_short_term_schema()

    char_name = config_service.get_config_value("system.char_name")
    character = None
    if char_name:
        character = character_service.get_or_create_character(char_name)
        refresh_recent_days(character.id)
        log_audit_entry(
            event_type="character_bootstrap",
            msg=get_text(
                "initialize.character_bootstrap",
                params={"char_name": char_name},
                default=f"[Initialize] ensured character '{char_name}' exists",
            ),
            status=AuditStatus.SUCCESS,
            message_key="initialize.character_bootstrap",
            message_args={"char_name": char_name},
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
            print(
                get_text(
                    "initialize.print_vision_started",
                    default="[Initialize] Визуальный сервис запущен",
                )
            )
        except Exception as e:
            print(
                get_text(
                    "initialize.print_vision_start_error",
                    params={"error": e},
                    default=f"[Initialize] Ошибка запуска визуального сервиса: {e}",
                )
            )

    print(
        get_text(
            "initialize.print_complete",
            params={"label": label},
            default="Initialization completed successfully.",
        )
    )
    log_audit_entry(
        event_type="startup_complete",
        msg=get_text(
            "initialize.startup_complete",
            params={"label": label},
            default=f"{label} Initialization complete",
        ),
        status=AuditStatus.SUCCESS,
        message_key="initialize.startup_complete",
        message_args={"label": label},
    )


def shutdown_services():
    """Shut down all services."""
    # ... other shutdown routines ...

    # Stop the vision service
    try:
        vision_service = VisionService()
        vision_service.stop()
        print(
            get_text(
                "initialize.print_vision_stopped",
                default="[Initialize] Визуальный сервис остановлен",
            )
        )
    except Exception as e:
        print(
            get_text(
                "initialize.print_vision_stop_error",
                params={"error": e},
                default=f"[Initialize] Ошибка остановки визуального сервиса: {e}",
            )
        )
