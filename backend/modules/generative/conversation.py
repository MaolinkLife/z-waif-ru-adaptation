"""High-level generation pipeline that orchestrates DecisionLayer and providers."""

from __future__ import annotations

import asyncio
import ast
import json
import re
import uuid
from datetime import datetime, timezone
import hashlib
from typing import Any, Awaitable, Callable, Dict, Iterable, List, Optional, Tuple

from modules.generative import NoProviderResolved, generation_manager
from modules.generative.types import GenerateRequest, GenerateStreamChunk
from core.decision_layer import decision_layer
from services import database_service
from services.config_service import get_config_value
from services.logger_service import AuditStatus, log_audit_entry
from modules.tts.state import VoiceStage, voice_state

THINK_PATTERN = re.compile(r"<think>(.*?)</think>", re.IGNORECASE | re.DOTALL)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _sanitize_media_items(media: Iterable[dict] | None) -> List[dict]:
    sanitized: List[dict] = []
    if not media:
        return sanitized
    for item in media:
        if not isinstance(item, dict):
            continue
        cleaned = {
            key: value
            for key, value in item.items()
            if key.lower() not in {"data", "base64"}
        }
        data_field = item.get("data") or item.get("base64")
        if data_field is not None and "size" not in cleaned:
            cleaned["size"] = len(data_field)
        sanitized.append(cleaned)
    return sanitized


def _extract_media_payload(message: Dict[str, Any] | Iterable[dict]) -> List[dict]:
    if isinstance(message, dict):
        media_items = message.get("media")
    else:
        media_items = message
    if not media_items:
        return []

    prepared: List[dict] = []
    for idx, item in enumerate(media_items):
        if not isinstance(item, dict):
            continue
        data = item.get("data") or item.get("base64")
        if not data:
            continue
        prepared.append(
            {
                "data": data,
                "mimeType": item.get("mimeType")
                or item.get("mime_type")
                or item.get("contentType")
                or item.get("type")
                or "",
                "category": item.get("category") or item.get("mediaType") or "other",
                "name": item.get("name")
                or item.get("filename")
                or f"attachment_{idx + 1}",
                "description": item.get("description") or "",
            }
        )
    return prepared


def _sanitize_history(history: list, *, drop_media: bool) -> list:
    sanitized: list = []
    for message in history or []:
        base = {k: v for k, v in message.items() if k != "timestamp"}
        media = base.get("media")
        if media:
            if drop_media:
                base.pop("media", None)
            else:
                base["media"] = _sanitize_media_items(media)
        sanitized.append(base)
    return sanitized


def build_chat_request(history: list) -> list:
    sanitized = _sanitize_history(history, drop_media=True)
    return [msg for msg in sanitized if msg.get("role") != "system"]


def split_reasoning(raw: str) -> tuple[str, str]:
    if not raw:
        return "", ""

    match = THINK_PATTERN.search(raw)
    if not match:
        return raw.strip(), ""

    reasoning = match.group(1).strip()
    cleaned = THINK_PATTERN.sub("", raw).strip()
    return cleaned, reasoning


def strip_reasoning_from_chunk(chunk: str, in_reasoning: bool) -> tuple[str, str, bool]:
    if not chunk:
        return "", "", in_reasoning

    speech_parts: list[str] = []
    reasoning_parts: list[str] = []
    lower_chunk = chunk.lower()
    idx = 0
    while idx < len(chunk):
        if in_reasoning:
            end_idx = lower_chunk.find("</think>", idx)
            if end_idx == -1:
                reasoning_parts.append(chunk[idx:])
                return "".join(speech_parts), "".join(reasoning_parts), True
            reasoning_parts.append(chunk[idx:end_idx])
            idx = end_idx + len("</think>")
            in_reasoning = False
        else:
            start_idx = lower_chunk.find("<think>", idx)
            if start_idx == -1:
                speech_parts.append(chunk[idx:])
                break
            speech_parts.append(chunk[idx:start_idx])
            idx = start_idx + len("<think>")
            in_reasoning = True

    return "".join(speech_parts), "".join(reasoning_parts), in_reasoning


def _extract_provider_errors(exc: Exception) -> List[Dict[str, str]]:
    try:
        data = ast.literal_eval(str(exc))
    except (ValueError, SyntaxError):
        return []

    if isinstance(data, dict):
        data = [data]

    errors: List[Dict[str, str]] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                provider = str(item.get("provider", "unknown"))
                reason = item.get("reason")
                if reason is None:
                    reason = ""
                errors.append({"provider": provider, "reason": str(reason)})
    return errors


def _generate_tags_for_text(
    text: str,
    extra: Iterable[str] | None = None,
    *,
    limit: int = 8,
) -> List[str]:
    tags: List[str] = []
    seen = set()
    for candidate in extra or []:
        normalized = str(candidate).strip()
        if not normalized:
            continue
        key = normalized.lower()
        if key in seen:
            continue
        seen.add(key)
        tags.append(normalized)
        if len(tags) >= limit:
            return tags
    for match in re.findall(r"[\w\-]{4,}", text.lower()):
        if match in seen:
            continue
        seen.add(match)
        tags.append(match)
        if len(tags) >= limit:
            break
    return tags


def _build_generation_options() -> dict:
    exclude = ["name", "description"]
    full_settings = get_config_value("generate_settings", {})
    return {k: v for k, v in full_settings.items() if k not in exclude}


def _voice_streaming_available() -> bool:
    return get_config_value("voice.enabled", False) and get_config_value(
        "voice.streaming_tts", False
    )


async def _ensure_voice_ready() -> None:
    retries = 5
    while voice_state.stage() is VoiceStage.PREPARING and retries > 0:
        await asyncio.sleep(0.2)
        retries -= 1


# ---------------------------------------------------------------------------
# Standard generation
# ---------------------------------------------------------------------------
async def generate_standard(
    decision_context: Dict[str, Any],
    history: list,
    last_user_message: Dict[str, Any],
    *,
    emit_ws_fn: Optional[Callable[[dict], Awaitable[None]]] = None,
    store: bool = True,
    return_full: bool = False,
) -> Dict[str, Any]:
    print("[Generator] Старт стандартной генерации.")
    sanitized_history = _sanitize_history(history, drop_media=True)
    log_audit_entry(
        event_type="conversation_standard_start",
        msg="[Conversation] Старт стандартной генерации",
        status=AuditStatus.INFO,
        details={
            "inputs": {"history": sanitized_history},
            "decision_keys": list(decision_context.keys()),
        },
    )

    if not last_user_message:
        raise ValueError("No user message found in history")

    system_prompt = decision_context.get("system_prompt", "")
    memory_context = decision_context.get("memory_context", {}) or {}
    memory_meta = decision_context.get("memory_meta", {}) or {}
    prompt_hash = hashlib.sha256(system_prompt.encode()).hexdigest()[:12]
    print("[Generator] Системный промпт готов для стандартного режима.")

    user_media_for_storage = _extract_media_payload(last_user_message) or None
    user_media_for_emit = _sanitize_media_items(
        last_user_message.get("media") if last_user_message else None
    )
    log_audit_entry(
        "conversation_prompt_ready",
        "[Conversation] Сформирован системный промпт для стандартной генерации.",
        AuditStatus.INFO,
        details={
            "prompt_length": len(system_prompt),
            "prompt_hash": prompt_hash,
            "history_length": len(history),
        },
    )

    if emit_ws_fn and last_user_message:
        await emit_ws_fn(
            {
                "type": "message",
                "role": "user",
                "content": last_user_message.get("content", ""),
                "id": last_user_message.get("id"),
                "timestamp": last_user_message.get("timestamp"),
                "media": user_media_for_emit,
            }
        )
        await emit_ws_fn({"type": "system", "event": "typing_start"})
        log_audit_entry(
            "conversation_user_message_emitted_standard",
            "[Conversation] Пользовательское сообщение отправлено (standard).",
            AuditStatus.INFO,
            details={
                "message_id": last_user_message.get("id"),
                "has_media": bool(user_media_for_emit),
                "media_count": len(user_media_for_emit),
            },
        )
        print("[Generator] Пользовательское сообщение отправлено (standard).")

    chat_history = build_chat_request(history)
    chat_history.insert(0, {"role": "system", "content": system_prompt})

    request_payload = GenerateRequest(
        messages=chat_history,
        options=_build_generation_options(),
        metadata={"mode": "standard"},
    )
    request_snapshot = {
        "messages": chat_history,
        "options": request_payload.options,
        "metadata": request_payload.metadata,
    }
    log_audit_entry(
        "conversation_standard_request_built",
        "[Conversation] Сформирован запрос стандартной генерации.",
        AuditStatus.INFO,
        details=request_snapshot,
    )
    print("[Generator] Запрос к провайдерам подготовлен (standard).")

    try:
        generate_result = generation_manager.generate(request_payload)
        print("[Generator] Провайдер вернул результат (standard).")
    except NoProviderResolved as exc:
        print("[Generator] Провайдеры недоступны (standard).")
        provider_errors = _extract_provider_errors(exc)
        log_audit_entry(
            event_type="generation_provider_failure",
            msg="[Generator] Не удалось подобрать провайдера",
            status=AuditStatus.ERROR,
            details={
                "errors": provider_errors
                if provider_errors
                else [{"provider": "unknown", "reason": str(exc)}],
                "request": request_snapshot,
            },
        )
        summary = "; ".join(
            f"{item['provider']}: {item['reason']}" for item in provider_errors
        )
        if emit_ws_fn:
            await emit_ws_fn({"type": "system", "event": "typing_end"})
            payload = {
                "type": "error",
                "message": "Generation provider not available",
            }
            if provider_errors:
                payload["details"] = provider_errors
            await emit_ws_fn(payload)
        raise RuntimeError(summary or "Generation provider not available") from exc

    assistant_raw = (generate_result.content or "").strip()
    assistant_content, assistant_reasoning = split_reasoning(assistant_raw)
    log_audit_entry(
        "conversation_standard_result",
        "[Conversation] Результат стандартной генерации получен.",
        AuditStatus.SUCCESS,
        details={
            "provider": generate_result.provider,
            "assistant_content_length": len(assistant_content),
            "assistant_reasoning_length": len(assistant_reasoning or ""),
            "metadata": generate_result.metadata,
        },
    )
    print("[Generator] Обработан ответ провайдера (standard).")

    if emit_ws_fn and last_user_message:
        await emit_ws_fn(
            {
                "type": "message",
                "role": "user",
                "content": last_user_message.get("content", ""),
            }
        )

    assistant_message_obj = None
    if store and assistant_content:
        memory_context_for_tags = memory_context
        extra_tags = list(memory_context_for_tags.get("short_term_themes") or [])
        user_tags = _generate_tags_for_text(
            last_user_message.get("content", ""), extra=extra_tags
        )
        database_service.add_message_to_history(
            character_name=get_config_value("system.char_name", "default"),
            role="user",
            content=last_user_message["content"],
            timestamp=datetime.now(timezone.utc),
            media=user_media_for_storage,
            tags=user_tags,
        )

        assistant_tags = _generate_tags_for_text(
            assistant_content, extra=extra_tags + ["assistant"]
        )
        assistant_message_obj = database_service.add_message_to_history(
            character_name=get_config_value("system.char_name", "default"),
            role="assistant",
            content=assistant_content,
            timestamp=datetime.now(timezone.utc),
            tags=assistant_tags,
        )
        if assistant_reasoning:
            database_service.add_reasoning_entry(
                assistant_message_obj.id,
                assistant_reasoning,
            )

    if emit_ws_fn and assistant_content:
        display_content = assistant_content
        if assistant_reasoning:
            display_content = f"<think>\n{assistant_reasoning}\n</think>\n\n{assistant_content}"
        await emit_ws_fn(
            {
                "type": "message",
                "role": "assistant",
                "content": display_content,
                "provider": generate_result.provider,
                "id": getattr(assistant_message_obj, "id", str(uuid.uuid4())),
                "timestamp": getattr(
                    assistant_message_obj, "timestamp", datetime.now(timezone.utc)
                ).isoformat(),
            }
        )
        await emit_ws_fn({"type": "system", "event": "typing_end"})
        log_audit_entry(
            "conversation_standard_emit_assistant",
            "[Conversation] Ответ ассистента отправлен (standard).",
            AuditStatus.INFO,
            details={
                "provider": generate_result.provider,
                "message_id": getattr(assistant_message_obj, "id", None),
            },
        )
        print("[Generator] Ответ ассистента отправлен (standard).")
    elif emit_ws_fn:
        await emit_ws_fn({"type": "system", "event": "typing_end"})

    decision_layer.handle_response(assistant_content)
    print("[Generator] Ответ передан в голосовой движок (standard).")

    if not return_full:
        log_audit_entry(
            "conversation_standard_complete",
            "[Conversation] Стандартная генерация завершена.",
            AuditStatus.INFO,
            details={
                "provider": generate_result.provider,
                "assistant_content": assistant_content,
                "assistant_reasoning": assistant_reasoning,
            },
        )
        print("[Generator] Стандартная генерация завершена.")
        return assistant_content

    timestamp_value = getattr(assistant_message_obj, "timestamp", None)
    if hasattr(timestamp_value, "isoformat"):
        timestamp_serialized = timestamp_value.isoformat()
    elif timestamp_value is None:
        timestamp_serialized = None
    else:
        timestamp_serialized = str(timestamp_value)

    display_content = assistant_content
    if assistant_reasoning:
        display_content = f"<think>\n{assistant_reasoning}\n</think>\n\n{assistant_content}"
    result_payload = {
        "id": getattr(assistant_message_obj, "id", None),
        "content": display_content,
        "timestamp": timestamp_serialized,
        "raw": assistant_raw,
        "reasoning": assistant_reasoning,
        "provider": generate_result.provider,
        "memory_meta": memory_meta,
    }
    log_audit_entry(
        "conversation_standard_complete_full",
        "[Conversation] Полный результат стандартной генерации подготовлен.",
        AuditStatus.INFO,
        details=result_payload,
    )
    print("[Generator] Стандартная генерация завершена (full).")
    return result_payload


# ---------------------------------------------------------------------------
# Streaming generation
# ---------------------------------------------------------------------------
async def generate_stream(
    decision_context: Dict[str, Any],
    history: list,
    *,
    emit_fn: Callable[[dict], Awaitable[bool]],
    last_user_message: Optional[Dict[str, Any]] = None,
    raw_user_media: Optional[Iterable[dict]] = None,
    store: bool = True,
) -> None:
    if not history:
        return

    system_prompt = decision_context.get("system_prompt", "")
    memory_context = decision_context.get("memory_context", {}) or {}

    if raw_user_media:
        user_media_for_storage = _extract_media_payload(raw_user_media)
    elif last_user_message:
        user_media_for_storage = _extract_media_payload(last_user_message)
    else:
        user_media_for_storage = None

    user_media_for_emit: List[dict] = []
    if last_user_message:
        user_media_for_emit = _sanitize_media_items(last_user_message.get("media"))

    prompt_hash = hashlib.sha256(system_prompt.encode()).hexdigest()[:12]
    print("[Generator] Подготовлен системный промпт для потока.")
    log_audit_entry(
        "conversation_prompt_ready_stream",
        "[Conversation] Сформирован системный промпт для потоковой генерации.",
        AuditStatus.INFO,
        details={
            "prompt_length": len(system_prompt),
            "prompt_hash": prompt_hash,
            "history_length": len(history),
        },
    )

    chat_history = build_chat_request(history)
    chat_history.insert(0, {"role": "system", "content": system_prompt})

    request_payload = GenerateRequest(
        messages=chat_history,
        options=_build_generation_options(),
        metadata={"mode": "stream"},
    )
    request_snapshot = {
        "messages": chat_history,
        "options": request_payload.options,
        "metadata": request_payload.metadata,
    }
    print("[Generator] Собрана заявка на потоковую генерацию.")

    stored_user_entry = None
    if store and last_user_message:
        extra_tags = list(memory_context.get("short_term_themes") or [])
        user_tags = _generate_tags_for_text(
            last_user_message.get("content", ""), extra=extra_tags
        )
        stored_user_entry = database_service.add_message_to_history(
            character_name=get_config_value("system.char_name", "default"),
            role="user",
            content=last_user_message.get("content", ""),
            timestamp=datetime.now(timezone.utc),
            media=user_media_for_storage,
            tags=user_tags,
        )
    if stored_user_entry and last_user_message:
        stored_media = getattr(stored_user_entry, "media_payload", []) or []
        user_media_for_emit = stored_media
        last_user_message["media"] = stored_media
    elif last_user_message:
        user_media_for_emit = _sanitize_media_items(last_user_message.get("media"))
        last_user_message["media"] = user_media_for_emit
    if last_user_message and emit_fn is not None:
        await emit_fn(
            {
                "type": "message",
                "role": "user",
                "content": last_user_message.get("content", ""),
                "id": last_user_message.get("id"),
                "timestamp": last_user_message.get("timestamp"),
                "media": user_media_for_emit,
            }
        )
        await emit_fn({"type": "system", "event": "typing_start"})
        log_audit_entry(
            "conversation_user_message_emitted_stream",
            "[Conversation] Пользовательское сообщение отправлено в поток.",
            AuditStatus.INFO,
            details={
                "message_id": last_user_message.get("id"),
                "has_media": bool(last_user_message.get("media")),
                "media_count": len(last_user_message.get("media") or []),
            },
        )

    voice_enabled = _voice_streaming_available()
    if voice_enabled:
        await _ensure_voice_ready()
        if voice_state.stage() is not VoiceStage.READY:
            voice_enabled = False

    print("[Generator] Потоковая генерация запущена.")
    log_audit_entry(
        "conversation_stream_started",
        "[Conversation] Потоковая генерация начата.",
        AuditStatus.INFO,
        details={
            "request": request_snapshot,
            "voice_enabled": voice_enabled,
        },
    )

    raw_chunks: List[str] = []
    speech_started = False
    streaming_in_reasoning = False
    provider_used_stream: Optional[str] = None
    assistant_message_obj = None
    chunk_meta: List[Dict[str, Any]] = []

    try:
        async for chunk in generation_manager.stream(request_payload):
            if provider_used_stream is None:
                provider_used_stream = chunk.provider

            content = chunk.content or ""
            if isinstance(content, str) and content:
                chunk_meta.append(
                    {
                        "provider": chunk.provider,
                        "length": len(content),
                        "done": chunk.done,
                        "has_reasoning": bool(chunk.reasoning),
                    }
                )
                if not await emit_fn(
                    {
                        "type": "message_chunk",
                        "role": "assistant",
                        "content": content,
                        "provider": provider_used_stream,
                    }
                ):
                    return

                raw_chunks.append(content)
                speech_chunk, _, streaming_in_reasoning = strip_reasoning_from_chunk(
                    content, streaming_in_reasoning
                )
                if voice_enabled and speech_chunk.strip():
                    voice_state.on_stream_chunk(speech_chunk)
                    if not speech_started:
                        voice_state.on_stream_start()
                        speech_started = True

        if voice_enabled and speech_started:
            voice_state.on_stream_end()
    except NoProviderResolved as exc:
        print("[Generator] Провайдеры недоступны для потока.")
        provider_errors = _extract_provider_errors(exc)
        payload: Dict[str, Any] = {
            "type": "error",
            "message": "Generation provider not available",
        }
        if provider_errors:
            payload["details"] = provider_errors
        await emit_fn(payload)
        await emit_fn({"type": "system", "event": "typing_end"})
        log_audit_entry(
            event_type="generation_provider_stream_failure",
            msg="[Generator] Потоковый провайдер недоступен",
            status=AuditStatus.ERROR,
            details={
                "errors": provider_errors
                if provider_errors
                else [{"provider": "unknown", "reason": str(exc)}],
                "request": request_snapshot,
            },
        )
        return

    assistant_raw = "".join(raw_chunks).strip()
    assistant_content, assistant_reasoning = split_reasoning(assistant_raw)
    print("[Generator] Потоковая генерация завершена.")
    log_audit_entry(
        "conversation_stream_completed",
        "[Conversation] Потоковая генерация завершена.",
        AuditStatus.SUCCESS,
        details={
            "provider": provider_used_stream,
            "chunks_received": len(chunk_meta),
            "chunk_details": chunk_meta,
            "assistant_response_length": len(assistant_content or ""),
            "assistant_reasoning_length": len(assistant_reasoning or ""),
        },
    )

    if assistant_content:
        extra_tags = list(memory_context.get("short_term_themes") or [])
        assistant_tags = _generate_tags_for_text(
            assistant_content, extra=extra_tags + ["assistant"]
        )
        assistant_message_obj = database_service.add_message_to_history(
            character_name=get_config_value("system.char_name", "default"),
            role="assistant",
            content=assistant_content,
            timestamp=datetime.now(timezone.utc),
            tags=assistant_tags,
        )
        if assistant_reasoning:
            database_service.add_reasoning_entry(
                assistant_message_obj.id,
                assistant_reasoning,
            )

    decision_layer.handle_response(assistant_content)
    assistant_timestamp = getattr(
        assistant_message_obj, "timestamp", datetime.now(timezone.utc)
    )
    assistant_message_id = getattr(assistant_message_obj, "id", str(uuid.uuid4()))
    display_content = assistant_content
    if assistant_reasoning:
        display_content = f"<think>\n{assistant_reasoning}\n</think>\n\n{assistant_content}"

    final_message_payload = {
        "type": "message",
        "role": "assistant",
        "content": display_content,
        "provider": provider_used_stream,
        "id": assistant_message_id,
        "timestamp": (
            assistant_timestamp.isoformat()
            if hasattr(assistant_timestamp, "isoformat")
            else str(assistant_timestamp)
        ),
        "media": [],
    }
    await emit_fn(final_message_payload)
    log_audit_entry(
        "conversation_stream_emit_end",
        "[Conversation] Финальный ответ отправлен клиенту.",
        AuditStatus.INFO,
        details={
            "provider": provider_used_stream,
            "assistant_content": assistant_content,
            "assistant_reasoning": assistant_reasoning,
            "message_id": assistant_message_id,
        },
    )
    await emit_fn(
        {
            "type": "message_end",
            "provider": provider_used_stream,
            "content": display_content,
            "reasoning": assistant_reasoning,
            "id": assistant_message_id,
        }
    )
    await emit_fn({"type": "system", "event": "typing_end"})


def play_message(msg_id: str):
    print("[Generator] Воспроизведение сохранённого сообщения.")
    message = database_service.get_message_by_id(msg_id)
    if get_config_value("voice.enabled", False):
        decision_layer.handle_response(message.get("content", ""))
    return message
