# ===========================================================
# Module: api_service.py
# Purpose: Generate a request for the model, including system prompt and clearing history
# Used in: ollama_routes (for preparing history)
# Features:
# - Loads a character's YAML profile
# - Removes unnecessary fields from history (e.g. timestamp)
# - Handles native Ollama HTTP errors (context length exceeded, OOM, etc.)
# ===========================================================

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Awaitable, Callable, Any, Dict, Iterable, List, Optional

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect

from modules.generative import NoProviderResolved, generation_manager
from modules.generative.types import GenerateRequest
from core.decision_layer import DecisionLayer
from services import database_service
from services.logger_service import log_audit_entry, AuditStatus
from modules.tts.state import VoiceStage, voice_state
from services.config_service import get_config_value
from services.database_service import get_message_by_id, add_message_to_history
from modules.memory import MemoryModule, MemoryContextResult
from utils.structure_utils import get_label_from_file
from core.prompt_loader import load_system_prompt
from core.emotion_intent_analyzer import analyze_emotion, generate_instruction


memory_module = MemoryModule()

def _render_memory_block(context: Dict[str, Any]) -> str:
    key_facts = context.get("key_facts") or []
    sections: List[str] = []
    if key_facts:
        facts_block = "\n".join(f"• {fact}" for fact in key_facts)
        sections.append("[MEMORY]\n" + facts_block)
    summary = context.get("short_term_summary")
    if summary:
        daily_block = "[DAILY SUMMARY]\n" + summary
        themes = context.get("short_term_themes") or []
        if themes:
            daily_block += "\nТемы: " + ', '.join(themes)
        sections.append(daily_block)
    return "\n\n".join(sections)


def _render_lore_block(context: Dict[str, Any]) -> str:
    lore_block = context.get("lore_block")
    if lore_block:
        if lore_block.strip().startswith("[CONTEXT]"):
            return lore_block
        return "[CONTEXT]\n" + lore_block
    matches = context.get("lore_matches") or []
    if matches:
        bullets = "\n".join(f"• {match}" for match in matches)
        return "[CONTEXT]\n" + bullets
    return ""



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


THINK_PATTERN = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


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


# ===========================================================
# History sanitization
# ===========================================================
def _sanitize_history(history: list, *, drop_media: bool) -> list:
    sanitized: list = []
    for message in history or []:
        base = {k: v for k, v in message.items() if k != "timestamp"}
        media = base.get("media")
        if media:
            if drop_media:
                base.pop("media", None)
            else:
                safe_media = []
                for item in media or []:
                    if isinstance(item, dict):
                        safe_media.append(
                            {k: v for k, v in item.items() if k != "data"}
                        )
                base["media"] = safe_media
        sanitized.append(base)
    return sanitized


# ===========================================================
# Build request
# ===========================================================
def build_chat_request(history, include_system=True):
    """
    System prompt is already embedded in history; we only strip timestamps.
    """
    return _sanitize_history(history, drop_media=True)


# ===========================================================
# Standard (non-streaming) generation
# ===========================================================
async def run_standard(
    history: list, emit_ws_fn=None, store: bool = True, return_full: bool = False
):
    log_audit_entry(
        event_type="ApiService.RunStandard",
        msg="[Api Service]: Generation function started",
        status=AuditStatus.INFO,
        details={"inputs": {"history": _sanitize_history(history, drop_media=False)}},
    )

    full_history = build_chat_request(history, include_system=False)
    char_name = get_config_value("char_name", "default")
    options = get_generation_options_from_config()
    last_user_message = extract_last_user_message(history)
    memory_result_data: Optional[MemoryContextResult] = None

    # Build system prompt with lore, memory, emotions
    system_prompt = None
    for msg in history:
        if msg.get("role") == "system":
            system_prompt = msg.get("content")
            break

    # Fallback to the default system prompt if none was supplied
    if not system_prompt:
        base_system_prompt = load_system_prompt()
        system_prompt = base_system_prompt
        # Only append memory and emotion blocks when using the fallback
        if last_user_message:
            memory_result = await memory_module.collect_context(
                last_user_message.get("content", ""), last_user_message
            )
            memory_result_data = memory_result
            memory_context = memory_result.context
            memory_block = _render_memory_block(memory_context)
            lore_block = _render_lore_block(memory_context)
            emotion_instruction = get_emotional_instruction(
                last_user_message["content"]
            )
            if lore_block:
                system_prompt += f"\n\n{lore_block}"
            if memory_block:
                system_prompt += f"\n\n{memory_block}"
            if emotion_instruction:
                system_prompt += f"\n\n[Emotional reaction]:\n{emotion_instruction}"

    full_history.insert(0, {"role": "system", "content": system_prompt})

    # === Call model ===
    request_payload = GenerateRequest(
        messages=full_history,
        options=options,
        metadata={"mode": "standard"},
    )

    try:
        generate_result = generation_manager.generate(request_payload)
    except NoProviderResolved as exc:
        log_audit_entry(
            event_type="generation_provider_failure",
            msg="[API] Не удалось подобрать провайдера генерации",
            status=AuditStatus.ERROR,
            details={"error": str(exc)},
        )
        raise RuntimeError("Generation provider not available") from exc

    assistant_raw = (generate_result.content or "").strip()
    raw_response = generate_result.raw
    assistant_content, assistant_reasoning = split_reasoning(assistant_raw)

    # === Save messages ===
    if last_user_message:
        if memory_result_data is None:
            memory_result_data = await memory_module.collect_context(
                last_user_message.get("content", ""), last_user_message
            )
        memory_context_for_tags = memory_result_data.context
        extra_tags = list(memory_context_for_tags.get("short_term_themes") or [])
        user_tags = _generate_tags_for_text(
            last_user_message.get("content", ""), extra=extra_tags
        )
        database_service.add_message_to_history(
            character_name=char_name,
            role="user",
            content=last_user_message["content"],
            timestamp=last_user_message.get("timestamp"),
            media=last_user_message.get("media"),
            tags=user_tags,
        )

    new_message_obj = None
    if store and assistant_content:
        if memory_result_data is None:
            memory_result_data = await memory_module.collect_context(
                assistant_content, {"content": assistant_content}
            )
        memory_context_for_tags = memory_result_data.context
        extra_tags = list(memory_context_for_tags.get("short_term_themes") or [])
        assistant_tags = _generate_tags_for_text(
            assistant_content, extra=extra_tags
        )
        new_message_obj = database_service.add_message_to_history(
            character_name=char_name,
            role="assistant",
            content=assistant_content,
            timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            tags=assistant_tags,
        )
        if assistant_reasoning:
            database_service.add_reasoning_entry(
                new_message_obj.id,
                assistant_reasoning,
            )

    # Voice
    if get_config_value("voice.enabled", False) and assistant_content:
        decision_layer_router.handle_response(assistant_content)

    # Logging
    log_audit_entry(
        event_type="generation_standard",
        msg="[API] Generate completed",
        status=AuditStatus.SUCCESS,
        details={
            "user_input": last_user_message["content"] if last_user_message else None,
            "assistant_output": assistant_content,
            "assistant_reasoning": assistant_reasoning,
            "provider": generate_result.provider,
        },
        meta={
            "source": "model",
            "mode": "standard",
            "provider": generate_result.provider,
            "full_response": raw_response,
            "assistant_raw": assistant_raw,
        },
    )

    # WS emit
    if emit_ws_fn and last_user_message:
        await emit_ws_fn(
            {"type": "message", "role": "user", "content": last_user_message["content"]}
        )
        await asyncio.sleep(0.005)
        if assistant_content:
            await emit_ws_fn(
                {"type": "message", "role": "assistant", "content": assistant_content}
            )

    if return_full:
        return {
            "id": new_message_obj.id if new_message_obj else None,
            "content": assistant_content,
            "timestamp": new_message_obj.timestamp if new_message_obj else None,
        }

    return assistant_content


# ===========================================================
# Streaming generation
# ===========================================================
async def run_stream_message(
    websocket: WebSocket | None,
    history: list,
    send_fn: Callable[[dict], Awaitable[bool]] | None = None,
):
    async def safe_send(payload: dict) -> bool:
        if send_fn is not None:
            try:
                await send_fn(payload)
                return True
            except Exception:
                return False
        if websocket is not None:
            try:
                await websocket.send_json(payload)
                return True
            except (WebSocketDisconnect, RuntimeError):
                return False
        return False

    log_audit_entry(
        event_type="ApiService.RunStream",
        msg="[Api Service]: Start streaming generation",
        status=AuditStatus.INFO,
        details={"inputs": {"history": _sanitize_history(history, drop_media=False)}},
    )

    await safe_send({"type": "system", "event": "typing_start"})

    try:
        full_history = build_chat_request(history, include_system=False)
        char_name = get_config_value("char_name", "default")
        options = get_generation_options_from_config()
        last_user_message = extract_last_user_message(history)
        memory_result_data: Optional[MemoryContextResult] = None

        # Extract system prompt from history or build a fallback
        system_prompt = None
        for msg in history:
            if msg.get("role") == "system":
                system_prompt = msg.get("content")
                break

        # Fallback to the default system prompt if none was supplied
        if not system_prompt:
            base_system_prompt = load_system_prompt()
            system_prompt = base_system_prompt
            # Only append memory and emotion blocks when using the fallback
            if last_user_message:
                memory_result = await memory_module.collect_context(
                    last_user_message.get("content", ""), last_user_message
                )
                memory_result_data = memory_result
                memory_context = memory_result.context
                memory_block = _render_memory_block(memory_context)
                lore_block = _render_lore_block(memory_context)
                emotion_instruction = get_emotional_instruction(
                    last_user_message["content"]
                )

                if lore_block:
                    system_prompt += f"\n\n{lore_block}"
                if memory_block:
                    system_prompt += f"\n\n{memory_block}"
                if emotion_instruction:
                    system_prompt += f"\n\n[Emotional reaction]:\n{emotion_instruction}"

        # Insert system prompt at the beginning of the history
        full_history.insert(0, {"role": "system", "content": system_prompt})

        # Save the user message and send ack back to the client
        user_message_obj = None
        if last_user_message:
            if memory_result_data is None:
                memory_result_data = await memory_module.collect_context(
                    last_user_message.get("content", ""), last_user_message
                )
            memory_context_for_tags = memory_result_data.context
            extra_tags = list(memory_context_for_tags.get("short_term_themes") or [])
            user_tags = _generate_tags_for_text(
                last_user_message.get("content", ""), extra=extra_tags
            )
            user_message_obj = add_message_to_history(
                character_name=char_name,
                role="user",
                content=last_user_message["content"],
                timestamp=normalize_timestamp(last_user_message.get("timestamp")),
                media=last_user_message.get("media"),
                tags=user_tags,
            )
            if last_user_message.get("id"):
                if not await safe_send(
                    {
                        "type": "ack_message",
                        "tempId": last_user_message.get("id"),
                        "realId": user_message_obj.id,
                        "media": getattr(user_message_obj, "media_payload", []),
                    }
                ):
                    return

        raw_chunks: list[str] = []
        streaming_in_reasoning = False
        voice_enabled = get_config_value("voice.enabled", False)
        streaming_tts = get_config_value("voice.streaming_tts", False)

        if voice_enabled and streaming_tts:
            log_audit_entry(
                "voice_streaming_unsupported",
                "[Voice] Streaming TTS not supported in current implementation",
                AuditStatus.WARNING,
            )
            streaming_tts = False

        speech_started = False
        provider_used_stream = None

        request_payload = GenerateRequest(
            messages=full_history,
            options=options,
            metadata={"mode": "stream"},
        )

        try:
            async for chunk in generation_manager.stream(request_payload):
                if provider_used_stream is None:
                    provider_used_stream = chunk.provider

                content = chunk.content or ""
                if isinstance(content, str) and content:
                    if not await safe_send(
                        {
                            "type": "message_chunk",
                            "role": "assistant",
                            "content": content,
                        }
                    ):
                        return
                    raw_chunks.append(content)

                    speech_chunk, _, streaming_in_reasoning = (
                        strip_reasoning_from_chunk(content, streaming_in_reasoning)
                    )

        except NoProviderResolved as exc:
            await safe_send(
                {"type": "error", "message": "Generation provider not available"}
            )
            log_audit_entry(
                event_type="generation_provider_stream_failure",
                msg="[API] Потоковый провайдер недоступен",
                status=AuditStatus.ERROR,
                details={"error": str(exc)},
            )
            return

        assistant_raw = "".join(raw_chunks).strip()
        assistant_content, assistant_reasoning = split_reasoning(assistant_raw)

        # Persist the assistant response
        assistant_message_obj = None
        if assistant_content:
            if memory_result_data is None:
                memory_result_data = await memory_module.collect_context(
                    assistant_content, {"content": assistant_content}
                )
            memory_context_for_tags = memory_result_data.context
            extra_tags = list(memory_context_for_tags.get("short_term_themes") or [])
            assistant_tags = _generate_tags_for_text(assistant_content, extra=extra_tags)
            assistant_message_obj = add_message_to_history(
                character_name=char_name,
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

        # Final message pushed to the client
        await safe_send(
            {
                "type": "message",
                "id": assistant_message_obj.id if assistant_message_obj else None,
                "role": "assistant",
                "content": assistant_raw,
            }
        )

        if voice_state.stage() == VoiceStage.WAITING:
            voice_state.enter_listening("generation_complete")

        if voice_enabled and not streaming_tts and assistant_content:
            decision_layer_router.handle_response(assistant_content)

        log_audit_entry(
            event_type="generation_stream",
            msg="[API] Stream generation completed",
            status=AuditStatus.SUCCESS,
            details={
                "user_input": (
                    last_user_message["content"] if last_user_message else None
                ),
                "assistant_output": assistant_content,
                "assistant_reasoning": assistant_reasoning,
            },
            meta={
                "source": "model",
                "mode": "stream",
                "provider": provider_used_stream,
                "full_response": assistant_raw,
            },
        )

    finally:
        await safe_send({"type": "system", "event": "stream_end"})


# ===========================================================
# Utils
# ===========================================================
def normalize_timestamp(ts):
    try:
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def get_emotional_instruction(message: str):
    analysis = analyze_emotion(message)
    return generate_instruction(analysis)


def get_generation_options_from_config(exclude: list = None) -> dict:
    exclude = exclude or ["name", "description"]
    full_settings = get_config_value("generate_settings", {})
    return {k: v for k, v in full_settings.items() if k not in exclude}


def extract_last_user_message(history):
    return next((msg for msg in reversed(history) if msg.get("role") == "user"), None)


# ===========================================================
# Playback
# ===========================================================
def play_message(msg_id: str):
    message = get_message_by_id(msg_id)
    if get_config_value("voice.enabled", False):
        decision_layer_router.handle_response(message.get("content", ""))
    return message


decision_layer_router = DecisionLayer()

