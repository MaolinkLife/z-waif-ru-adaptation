"""Embedding helpers for memory and lorebook subsystems."""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from threading import Lock
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

import requests
from requests import Response
from sentence_transformers import SentenceTransformer

_LOG_LEVEL = os.getenv("EMBED_SVC_LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=_LOG_LEVEL, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("memory.embeddings")

OLLAMA_URL: str = os.getenv("OLLAMA_EMBED_URL", "http://localhost:11434/api/embeddings")
OLLAMA_DEFAULT_MODEL: str = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_TIMEOUT_SEC: float = float(os.getenv("OLLAMA_TIMEOUT_SEC", "30"))
OLLAMA_MAX_RETRIES: int = int(os.getenv("OLLAMA_MAX_RETRIES", "2"))
OLLAMA_RETRY_BACKOFF_SEC: float = float(os.getenv("OLLAMA_RETRY_BACKOFF_SEC", "0.75"))

DEFAULT_ST_MODEL_NAME: str = os.getenv(
    "ST_DEFAULT_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
)

OLLAMA_TO_ST_FALLBACK: Dict[str, str] = {
    "nomic-embed-text": DEFAULT_ST_MODEL_NAME,
}

TRUST_REMOTE_CODE_ORGS: Tuple[str, ...] = ("nomic-ai/",)


class EmbeddingError(Exception):
    """Base embedding error."""


class OllamaError(EmbeddingError):
    """Raised for Ollama-specific failures."""


class STModelError(EmbeddingError):
    """Raised for SentenceTransformers-specific failures."""


_st_model_lock = Lock()
_st_models_cache: Dict[str, SentenceTransformer] = {}


def _should_trust_remote_code(model_name: str) -> bool:
    return any(model_name.startswith(org) for org in TRUST_REMOTE_CODE_ORGS)


def _normalize_st_model_name(name: Optional[str]) -> str:
    if not name:
        return DEFAULT_ST_MODEL_NAME
    if "/" not in name:
        return OLLAMA_TO_ST_FALLBACK.get(name, DEFAULT_ST_MODEL_NAME)
    return name


def _load_st_model(model_name: str) -> Optional[SentenceTransformer]:
    try:
        trust = _should_trust_remote_code(model_name)
        model = SentenceTransformer(model_name, trust_remote_code=trust)
        return model
    except Exception as exc:
        logger.error("ST model load failed [%s]: %s", model_name, exc)
        return None


def _get_st_model(model_name: Optional[str] = None) -> Optional[SentenceTransformer]:
    name = _normalize_st_model_name(model_name)

    with _st_model_lock:
        cached = _st_models_cache.get(name)
        if cached is not None:
            return cached

        model = _load_st_model(name)
        if model is not None:
            _st_models_cache[name] = model
        return model


def _safe_read_text(res: Optional[Response]) -> str:
    try:
        return res.text if res is not None else ""
    except Exception:
        return ""


def _post_with_retries(
    url: str, json_payload: dict, timeout: float, max_retries: int, backoff: float
) -> Response:
    last_exc: Optional[Exception] = None
    res: Optional[Response] = None

    for attempt in range(max_retries + 1):
        try:
            res = requests.post(url, json=json_payload, timeout=timeout)
            if 200 <= res.status_code < 300:
                return res
            if 400 <= res.status_code < 500:
                raise OllamaError(
                    f"Ollama HTTP {res.status_code}: {res.reason} | body={_safe_read_text(res)[:400]}"
                )
            last_exc = OllamaError(
                f"Ollama HTTP {res.status_code}: {res.reason} | body={_safe_read_text(res)[:400]}"
            )
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_exc = exc

        if attempt < max_retries:
            sleep_for = backoff * (2**attempt)
            time.sleep(sleep_for)

    assert last_exc is not None
    raise OllamaError(f"Ollama request failed after retries: {last_exc}")


# Ollama embeddings ---------------------------------------------------------


def _ollama_embed_one(text: str, model: str) -> Optional[List[float]]:
    payload = {"model": model, "prompt": text}
    try:
        res = _post_with_retries(
            OLLAMA_URL,
            json_payload=payload,
            timeout=OLLAMA_TIMEOUT_SEC,
            max_retries=OLLAMA_MAX_RETRIES,
            backoff=OLLAMA_RETRY_BACKOFF_SEC,
        )
        data = res.json()
        vector = data.get("embedding")
        if not vector:
            logger.warning("Ollama returned empty embedding for prompt len=%s", len(text))
            return None
        return vector
    except (OllamaError, ValueError, json.JSONDecodeError) as exc:
        logger.error("Ollama embedding failure: %s", exc)
        return None


def get_embedding_ollama(text: str, model: str = OLLAMA_DEFAULT_MODEL) -> Optional[List[float]]:
    return _ollama_embed_one(text, model)


def get_embeddings_ollama(
    texts: Iterable[str],
    model: str = OLLAMA_DEFAULT_MODEL,
) -> List[Optional[List[float]]]:
    vectors: List[Optional[List[float]]] = []
    for chunk in texts:
        vectors.append(get_embedding_ollama(chunk, model=model))
    return vectors


# SentenceTransformer embeddings -------------------------------------------


def _st_embed(texts: Sequence[str], model_name: Optional[str] = None) -> Optional[List[List[float]]]:
    model = _get_st_model(model_name)
    if model is None:
        return None

    try:
        embeddings = model.encode(
            list(texts), convert_to_numpy=False, show_progress_bar=False
        )
        normalized: List[List[float]] = []
        for vec in embeddings:
            if hasattr(vec, "detach"):
                normalized.append(vec.detach().cpu().tolist())
            elif hasattr(vec, "tolist"):
                normalized.append(vec.tolist())
            else:
                normalized.append(list(vec))
        return normalized
    except Exception as exc:
        raise STModelError(str(exc)) from exc


def get_embedding_st(text: str, model: Optional[str] = None) -> Optional[List[float]]:
    batch = _st_embed([text], model_name=model)
    return batch[0] if batch else None


def get_embeddings_st(texts: Sequence[str], model: Optional[str] = None) -> List[Optional[List[float]]]:
    batch = _st_embed(texts, model_name=model)
    if batch is None:
        return [None for _ in texts]
    return batch


# Unified API ---------------------------------------------------------------


@dataclass(frozen=True)
class Provider:
    OLLAMA: str = "ollama"
    ST: str = "st"
    AUTO: str = "auto"


def _as_text_list(text_or_texts: Union[str, Sequence[str]]) -> List[str]:
    if isinstance(text_or_texts, str):
        return [text_or_texts]
    return list(text_or_texts)


def get_embedding(
    text: str,
    provider: str = Provider.AUTO,
    model: str = OLLAMA_DEFAULT_MODEL,
) -> Optional[List[float]]:
    p = (provider or Provider.AUTO).lower()

    if p == Provider.OLLAMA:
        return get_embedding_ollama(text, model=model)

    if p == Provider.ST:
        return get_embedding_st(text, model=model)

    if p == Provider.AUTO:
        vec = get_embedding_ollama(text, model=model)
        return vec if vec is not None else get_embedding_st(text, model=model)

    raise ValueError(f"Unknown provider: {provider}")


def get_embeddings(
    texts: Union[str, Sequence[str]],
    provider: str = Provider.AUTO,
    model: str = OLLAMA_DEFAULT_MODEL,
) -> List[Optional[List[float]]]:
    p = (provider or Provider.AUTO).lower()
    items = _as_text_list(texts)

    if p == Provider.OLLAMA:
        return get_embeddings_ollama(items, model=model)

    if p == Provider.ST:
        return get_embeddings_st(items, model=model)

    if p == Provider.AUTO:
        res = get_embeddings_ollama(items, model=model)
        need_fallback_indices = [i for i, v in enumerate(res) if v is None]
        if not need_fallback_indices:
            return res

        fallback_inputs = [items[i] for i in need_fallback_indices]
        fallback_vecs = get_embeddings_st(fallback_inputs, model=model)

        it = iter(fallback_vecs)
        for i in need_fallback_indices:
            res[i] = next(it, None)
        return res

    raise ValueError(f"Unknown provider: {provider}")


def get_both_embeddings(text: str) -> tuple[Optional[List[float]], Optional[List[float]]]:
    embedding_384 = get_embedding_st(text)
    embedding_768 = get_embedding_ollama(text)
    return embedding_384, embedding_768


def get_embeddings_batch_both(
    texts: Sequence[str],
) -> tuple[List[Optional[List[float]]], List[Optional[List[float]]]]:
    embeddings_384 = get_embeddings_st(texts)
    embeddings_768 = get_embeddings_ollama(texts)
    return embeddings_384, embeddings_768
