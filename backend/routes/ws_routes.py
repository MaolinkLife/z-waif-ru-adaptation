import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.websocket_manager import manager
from modules.generative import conversation
from services import database_service, config_service
from services.logger_service import log_audit_entry, AuditStatus
from core.decision_layer import decision_layer

ws_router = APIRouter(prefix="/api", tags=["WebSocket"])




async def _safe_send_json(websocket: WebSocket, payload: dict) -> bool:
    try:
        await websocket.send_json(payload)
        return True
    except (WebSocketDisconnect, RuntimeError):
        return False


@ws_router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            try:
                raw_data = await websocket.receive_text()
            except WebSocketDisconnect:
                break
            except RuntimeError:
                # WebSocket may not be connected or already closed
                break

            log_audit_entry(
                'ws_receive',
                '[WS] Received payload from client.',
                AuditStatus.INFO,
                details={'size': len(raw_data)},
            )

            try:
                payload = json.loads(raw_data)
            except json.JSONDecodeError:
                if not await _safe_send_json(
                    websocket, {"type": "error", "message": "Invalid JSON"}
                ):
                    break
                continue

            action = payload.get("action")
            data = payload.get("payload", {})

            if not action:
                if not await _safe_send_json(
                    websocket, {"type": "error", "message": "Missing 'action'"}
                ):
                    break
                continue

            # === ROUTING ===
            if action == "send_message":
                try:
                    from core.instructor import Instructor

                    # Retrieve processed context from the DecisionLayer
                    processing_result = await decision_layer.process_message(
                        data, websocket
                    )

                    # Format history for the API service
                    instructor = Instructor()
                    raw_media_payload = processing_result.pop("raw_media", None)
                    media_payload = (
                        raw_media_payload
                        if raw_media_payload is not None
                        else data.get("media")
                    )
                    if media_payload:
                        log_audit_entry(
                            "ws_media_received",
                            "[WS] Incoming media payload for send_message.",
                            AuditStatus.INFO,
                            details={"count": len(media_payload)},
                        )
                        visual_context = processing_result.get("visual_context") or {}
                        attachments_info = (visual_context.get("attachments") or {}).get("items", [])
                        applied = 0
                        for item in attachments_info:
                            idx = item.get("index")
                            description = (item.get("description") or "").strip()
                            if (
                                isinstance(idx, int)
                                and 0 <= idx < len(media_payload)
                                and description
                            ):
                                media_payload[idx]["description"] = description
                                applied += 1
                        if applied:
                            log_audit_entry(
                                "ws_media_described",
                                "[WS] Image attachments described via decision layer vision.",
                                AuditStatus.INFO,
                                details={"count": applied},
                            )
                        elif attachments_info:
                            log_audit_entry(
                                "ws_media_description_missing",
                                "[WS] Vision module returned attachment metadata without summaries.",
                                AuditStatus.WARNING,
                                details={"count": len(attachments_info)},
                            )

                    formatted_history = await instructor.format_for_api(
                        processing_result["system_prompt"],
                        processing_result["user_message"],
                    )

                    async def emit(payload: dict) -> bool:
                        return await _safe_send_json(websocket, payload)

                    await conversation.generate_stream(
                        processing_result,
                        formatted_history,
                        emit_fn=emit,
                        last_user_message=processing_result.get("user_message"),
                        raw_user_media=media_payload,
                    )

                except Exception as e:
                    log_audit_entry(
                        'ws_send_message_error',
                        '[WS] Error while processing message.',
                        AuditStatus.ERROR,
                        details={'error': str(e)},
                    )
                    import traceback

                    traceback.print_exc()  # For debugging
                    if not await _safe_send_json(
                        websocket, {"type": "error", "message": str(e)}
                    ):
                        break

            elif action == "fetch_history":
                limit = data.get("limit", 32)
                offset = data.get("offset", 0)
                char_name = config_service.get_config_value(
                    "system.char_name", "default_waifu"
                )
                history = database_service.get_history(char_name, limit, offset)
                if not await _safe_send_json(
                    websocket, {"type": "history", "items": history}
                ):
                    break

            elif action == "delete_message":
                message_id = data.get("message_id")
                chain = data.get("chain", False)
                if not message_id:
                    if not await _safe_send_json(
                        websocket, {"type": "error", "message": "message_id required"}
                    ):
                        break
                else:
                    if chain:
                        database_service.delete_message_chain(message_id)
                        if not await _safe_send_json(
                            websocket,
                            {
                                "type": "deleted",
                                "message_id": message_id,
                                "chain": True,
                            },
                        ):
                            break
                    else:
                        database_service.delete_message(message_id)
                        if not await _safe_send_json(
                            websocket,
                            {
                                "type": "deleted",
                                "message_id": message_id,
                                "chain": False,
                            },
                        ):
                            break

            elif action == "reroll_message":
                message_id = data.get("message_id")
                if not message_id:
                    if not await _safe_send_json(
                        websocket, {"type": "error", "message": "message_id required"}
                    ):
                        break
                else:
                    new_msg = await database_service.reroll_message(
                        message_id
                    )  # Added await
                    if not await _safe_send_json(
                        websocket,
                        {
                            "type": "reroll",
                            "old_id": message_id,
                            "new_message": new_msg,
                        },
                    ):
                        break

            else:
                if not await _safe_send_json(
                    websocket,
                    {"type": "error", "message": f"Unknown action '{action}'"},
                ):
                    break

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        log_audit_entry(
            'ws_disconnect',
            '[WS] Client disconnected.',
            AuditStatus.INFO,
        )
    finally:
        manager.disconnect(websocket)
