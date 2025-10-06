# ==========================================================
# Module: vector_service.py
# Purpose: Manage vector DB (Chroma) for semantic memory
# ==========================================================

import uuid
import chromadb


CHROMA_DIR = "./storage/vector_store"

_client = chromadb.PersistentClient(path=CHROMA_DIR)


def _get_collection(name: str = "pai_memory"):
    return _client.get_or_create_collection(
        name=name, metadata={"hnsw:space": "cosine"}
    )


def add_texts(
    texts,
    embeddings,
    metadatas=None,
    ids=None,
    collection_name: str = "pai_memory",
):
    collection = _get_collection(collection_name)

    if metadatas is None:
        metadatas = [{"source": "manual"} for _ in texts]

    if ids is None:
        ids = [f"doc_{uuid.uuid4()}" for _ in texts]

    collection.add(
        ids=ids,
        documents=texts,
        embeddings=embeddings,
        metadatas=metadatas,
    )


def upsert_text(
    doc_id: str,
    text: str,
    embedding,
    metadata: dict | None = None,
    collection_name: str = "pai_memory",
):
    collection = _get_collection(collection_name)
    collection.upsert(
        ids=[doc_id],
        documents=[text],
        embeddings=[embedding],
        metadatas=[metadata or {}],
    )


def delete_text(doc_id: str, collection_name: str = "pai_memory"):
    collection = _get_collection(collection_name)
    collection.delete(ids=[doc_id])


def search(query_embedding, top_k=3, collection_name: str = "pai_memory"):
    """Find the nearest documents by embedding."""
    collection = _get_collection(collection_name)
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )
    return results


def reset(collection_name: str = "pai_memory"):
    """Полностью очистить коллекцию и пересоздать с cosine similarity."""
    _client.delete_collection(collection_name)
    _get_collection(collection_name)
