"""HTTP client helpers for interacting with the local Ollama server."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator, Dict, Iterable, Optional

import aiohttp
import requests

from services.config_service import get_config_value
from services.logger_service import AuditStatus, log_audit_entry, log_error
from services.localization_service import get_text

OLLAMA_API_URL = "http://localhost:11434/api"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _resolve_text_model(model: Optional[str]) -> str:
    return model or get_config_value("api.model")


def get_visual_model() -> str:
    return get_config_value("api.visual_model")


# ---------------------------------------------------------------------------
# Chat helpers
# ---------------------------------------------------------------------------

def _messages_to_prompts(messages: Iterable[Dict[str, Any]]) -> tuple[str, str]:
    system_segments: list[str] = []
    dialogue_segments: list[str] = []

    for message in messages:
        role = (message or {}).get("role")
        content = (message or {}).get("content", "")
        if not content:
            continue
        if role == "system":
            system_segments.append(content)
        elif role == "user":
            dialogue_segments.append(f"User: {content}")
        elif role == "assistant":
            dialogue_segments.append(f"Assistant: {content}")
        else:
            dialogue_segments.append(content)

    system_prompt = "\n\n".join(system_segments).strip()
    prompt = "\n\n".join(dialogue_segments).strip()
    return system_prompt, prompt


def _chat_via_generate(
    messages: Iterable[Dict[str, Any]],
    options: Dict[str, Any],
    model: str,
) -> Dict[str, Any]:
    system_prompt, prompt = _messages_to_prompts(messages)
    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt or "",
        "stream": False,
        "options": options,
    }
    if system_prompt:
        payload["system"] = system_prompt

    response = requests.post(
        f"{OLLAMA_API_URL}/generate",
        json=payload,
        timeout=300,
    )
    response.raise_for_status()
    data = response.json()
    text = data.get("response", "")
    return {
        "message": {
            "role": "assistant",
            "content": text,
        }
    }


def chat(messages: Iterable[Dict[str, Any]], options: Dict[str, Any], model: str | None = None) -> Dict[str, Any]:
    ollama_model = _resolve_text_model(model)
    payload = {
        "model": ollama_model,
        "messages": list(messages),
        "options": options,
        "stream": False,
    }
    try:
        response = requests.post(
            f"{OLLAMA_API_URL}/chat",
            json=payload,
            timeout=300,
        )
        if response.status_code == 404:
            return _chat_via_generate(messages, options, ollama_model)

        response.raise_for_status()
        data = response.json()

        if "error" in data:
            log_audit_entry(
                event_type="ollama_error",
                msg=get_text(
                    "logger.ollama_error",
                    params={"error": data["error"]},
                    default=f"[Ollama] Error: {data['error']}",
                ),
                status=AuditStatus.ERROR,
                details={"model": ollama_model, "error": data["error"]},
                message_key="logger.ollama_error",
                message_args={"error": data["error"]},
            )
            raise RuntimeError(data["error"])

        return data
    except Exception as exc:
        log_error(f"[Ollama] HTTP error: {exc}")
        raise


async def stream_chat(
    messages: Iterable[Dict[str, Any]],
    options: Dict[str, Any],
    model: str | None = None,
) -> AsyncIterator[Dict[str, Any]]:
    ollama_model = _resolve_text_model(model)
    url = f"{OLLAMA_API_URL}/chat"
    payload = {
        "model": ollama_model,
        "messages": list(messages),
        "options": options,
        "stream": True,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            async for line in resp.content:
                if not line.strip():
                    continue
                try:
                    data = line.decode("utf-8").strip()
                    obj = json.loads(data)
                    if "error" in obj:
                        yield {"error": obj["error"]}
                        return
                    yield obj
                except Exception as exc:
                    log_error(f"[Ollama stream parse error]: {exc}")
                    return


# ---------------------------------------------------------------------------
# Visual helpers
# ---------------------------------------------------------------------------

def chat_image(messages: Iterable[Dict[str, Any]]) -> str:
    ollama_model_visual = get_visual_model()
    payload = {
        "model": ollama_model_visual,
        "messages": list(messages),
        "stream": False,
    }
    try:
        response = requests.post(
            f"{OLLAMA_API_URL}/chat",
            json=payload,
            timeout=300,
        )
        response.raise_for_status()
        data = response.json()

        if "error" in data:
            log_error(f"[Ollama visual error]: {data['error']}")
            return f"[ERROR] {data['error']}"

        return data.get("message", {}).get("content", "")
    except Exception as exc:
        log_error(f"[Ollama visual HTTP error]: {exc}")
        return "[ERROR] Visual model request failed."


async def stream_chat_image(messages: Iterable[Dict[str, Any]]) -> AsyncIterator[Dict[str, Any]]:
    ollama_model_visual = get_visual_model()
    url = f"{OLLAMA_API_URL}/chat"
    payload = {
        "model": ollama_model_visual,
        "messages": list(messages),
        "stream": True,
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload) as resp:
            async for line in resp.content:
                if not line.strip():
                    continue
                try:
                    data = line.decode("utf-8").strip()
                    obj = json.loads(data)
                    if "error" in obj:
                        yield {"error": obj["error"]}
                        return
                    yield obj
                except Exception as exc:
                    log_error(f"[Ollama visual stream parse error]: {exc}")
                    return


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def is_available() -> bool:
    try:
        response = requests.get(f"{OLLAMA_API_URL}/tags", timeout=5)
        return response.status_code == 200
    except Exception:
        return False


def list_models() -> Dict[str, Any]:
    if not is_available():
        return {
            "status": "error",
            "message": "Ollama not installed, not running or not accessible",
        }

    try:
        response = requests.get(f"{OLLAMA_API_URL}/tags", timeout=10)
        response.raise_for_status()
        data = response.json()
        models = [m["name"] for m in data.get("models", [])]
        return {"status": "ok", "models": models}
    except Exception as exc:
        return {"status": "error", "message": f"Ollama error: {exc}"}
