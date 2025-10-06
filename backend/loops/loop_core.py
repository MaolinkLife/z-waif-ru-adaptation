from threading import Thread
from loops.loop_initiative import initiative_monitor
from services.logger_service import log_audit_entry, AuditStatus
# from loops.loop_emotion import emotion_drift_monitor   ← (planned for later)
# from loops.loop_anchors import anchor_check_monitor    ← (planned for later)

def run_loop():
    Thread(target=initiative_monitor, daemon=True).start()
    # Thread(target=emotion_drift_monitor, daemon=True).start()
    # Thread(target=anchor_check_monitor, daemon=True).start()
    log_audit_entry(
        event_type="loop_started",
        msg="[Initiative] Loop system запущен",
        status=AuditStatus.INFO, 
        details={"loop": "initiative_monitor"}
    )
