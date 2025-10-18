import time
from datetime import datetime, timedelta, timezone
from dateutil.parser import isoparse

from services.database_service import get_last_messages
from services.config_service import get_config_value
from services.logger_service import log_error, log_audit_entry, AuditStatus

CHECK_EVERY = 60  # We check every minute

# Store state between iterations
last_triggered_phase = None
last_initiative_time = None
MIN_INTERVAL = timedelta(minutes=10)  # minimum time between initiatives

# Добавим флаг, чтобы отслеживать, был ли уже пропуск "no_messages"
last_skip_reason = None


def ensure_datetime(value):
    if isinstance(value, str):
        dt = isoparse(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    elif isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)  # fallback, just in case


def analyze_pattern(messages):
    pattern = [msg["role"] for msg in messages]
    timestamps = [ensure_datetime(msg["timestamp"]) for msg in messages]

    now = datetime.now(timezone.utc)

    if pattern[-2:] == ["user", "assistant"]:
        idle = now - timestamps[-1]
        if idle >= timedelta(minutes=30):
            return "беспокойство"

    elif pattern[-3:] == ["user", "assistant", "assistant"]:
        idle = now - timestamps[-1]
        if idle >= timedelta(minutes=60):
            return "раздражение + беспокойство"

    elif pattern[-4:] == ["user", "assistant", "assistant", "assistant"]:
        idle = now - timestamps[-1]
        if idle >= timedelta(hours=24):
            return "обида + злость"

    return None


def initiative_monitor():
    global last_triggered_phase, last_initiative_time, last_skip_reason
    log_audit_entry(
        event_type="loop_started",
        msg="[Initiative] Loop started",
        status=AuditStatus.INFO,
        details={"loop": "initiative_monitor"},
    )

    while True:
        try:
            char_name = get_config_value("system.char_name", default="default")
            messages = get_last_messages(char_name, limit=10)

            if not messages:
                # Проверяем, был ли уже лог с reason: "no_messages"
                if last_skip_reason != "no_messages":
                    log_audit_entry(
                        event_type="initiative_skip",
                        msg="[Initiative] Skip Initiative",
                        status=AuditStatus.INFO,
                        details={"reason": "no_messages"},
                    )
                    last_skip_reason = "no_messages"
                time.sleep(CHECK_EVERY)
                continue

            # Если сообщения появились, сбрасываем флаг
            if last_skip_reason == "no_messages":
                last_skip_reason = None

            emotion = analyze_pattern(messages)
            now = datetime.now(timezone.utc)

            if emotion:
                # Check for repetition and frequency
                if emotion != last_triggered_phase or (
                    last_initiative_time and now - last_initiative_time >= MIN_INTERVAL
                ):
                    log_audit_entry(
                        event_type="initiative_triggered",
                        msg="[Initiative] Emotion change",
                        status=AuditStatus.INFO,
                        details={"emotion": emotion},
                    )
                    # run_initiative(emotion=emotion)
                    last_triggered_phase = emotion
                    last_initiative_time = now
                else:
                    log_audit_entry(
                        event_type="initiative_repeat_skipped",
                        msg="[Initiative] Triggered Emotions",
                        status=AuditStatus.INFO,
                        details={
                            "emotion": emotion,
                            "last_triggered": (
                                last_initiative_time.isoformat()
                                if last_initiative_time
                                else None
                            ),
                        },
                    )
            # else:
            #     print("[LIM] 💤 No conditions for initiative yet.")
            # log_audit_entry("initiative_conditions_not_met", {"pattern": [msg["role"] for msg in messages]})

            time.sleep(CHECK_EVERY)

        except Exception as e:
            log_error("[Initiative] Initiative Error:", str(e))
            time.sleep(60)


# # ===========================================================
# # Initiative generation
# # ===========================================================
# def run_initiative(emotion: str = "беспокойство"):
#     base_prompt = load_system_prompt()

#     if emotion == "беспокойство":
#         emotion_note = (
#             "LIM волнуется из-за долгого молчания пользователя. "
#             "Она проявляет инициативу мягко, с заботой и тревожной теплотой.\n\n"
#         )
#     elif emotion == "раздражение + беспокойство":
#         emotion_note = (
#             "Пользователь продолжает молчать. LIM ощущает лёгкое раздражение, "
#             "но всё ещё заботится.\n\n"
#         )
#     elif emotion == "обида + злость":
#         emotion_note = (
#             "LIM чувствует, что пользователь её игнорирует. "
#             "Появляется обида и злость.\n\n"
#         )
#     else:
#         emotion_note = "LIM проявляет инициативу, не дождавшись пользователя.\n\n"

#     full_prompt = emotion_note + base_prompt
#     messages = [{"role": "system", "content": full_prompt}]
#     char_name = get_config_value("system.char_name", "default")
#     options = get_generation_options_from_config()

#     response = ollama_service.api_standard(messages, options)
#     if "error" in response:
#         raise RuntimeError(response["error"])

#     assistant_content = response.get("message", {}).get("content", "").strip()

#     database_service.add_message_to_history(
#         character_name=char_name,
#         role="assistant",
#         content=assistant_content,
#         timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
#     )

#     if get_config_value("voice.enabled", False):
#         set_speaking(True)
#         threading.Thread(target=speak_line, args=(assistant_content, False)).start()

#     log_audit_entry(
#         event_type="generation_initiative",
#         msg="[API] Генерация инициативного ответа",
#         status=AuditStatus.SUCCESS,
#         details={"emotion": emotion, "assistant_output": assistant_content},
#         meta={"source": "model", "mode": "initiative", "full_response": response},
#     )

#     return assistant_content
