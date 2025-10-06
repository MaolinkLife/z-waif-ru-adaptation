from fastapi import APIRouter
from fastapi.responses import JSONResponse
from services.logger_service import get_debug_log

router = APIRouter(prefix="/api/log", tags=["Logs"])


@router.get("/")
def get_current_session_log():
    try:
        logs, session_id = get_debug_log()
        if logs is None:
            return JSONResponse(
                status_code=404, content={"error": "Log file not found"}
            )

        return {"session_id": session_id, "logs": logs}

    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": "Error processing request", "details": str(e)},
        )
