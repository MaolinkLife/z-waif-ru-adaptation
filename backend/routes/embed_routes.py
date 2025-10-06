# ==========================================================
# Module: embed_routes.py
# Purpose: FastAPI endpoints for embeddings
# ==========================================================

from fastapi import APIRouter, Query
from modules.memory import embeddings

router = APIRouter(prefix="/api/embed", tags=["embeddings"])


@router.get("/test")
def test_embedding(
    q: str = Query("Hello world test", description="Текст для эмбеддинга"),
    provider: str = Query("auto", description="Провайдер: auto | ollama | st"),
    model: str = Query(
        "nomic-embed-text", description="Модель Ollama (если используется)"
    ),
):
    emb = embeddings.get_embedding(q, provider=provider, model=model)

    return {
        "provider": provider,
        "model": model,
        "text": q,
        "length": len(emb) if emb else 0,
        "embedding_preview": emb[:10] if emb else [],
    }
