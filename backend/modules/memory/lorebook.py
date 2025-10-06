"""Lorebook utilities cooperating with the vector store and embeddings."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from models.models import LorebookEntry
from services.db_core import SessionLocal
from services.logger_service import AuditStatus, log_audit_entry
from services import vector_service

from . import embeddings

LOREBOOK_COLLECTION_384 = "pai_lorebook_384"
LOREBOOK_COLLECTION_768 = "pai_lorebook_768"


def _entry_to_dict(entry: LorebookEntry) -> Dict[str, Any]:
    return {
        "id": entry.id,
        "title": entry.title,
        "content": entry.content,
        "keywords": entry.keywords,
        "category": entry.category,
        "active": entry.active,
        "created_at": entry.created_at.isoformat() if entry.created_at else None,
        "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
    }


def _compose_document(entry: LorebookEntry) -> str:
    parts = [entry.title or "", entry.content or "", entry.keywords or ""]
    return "\n".join(part.strip() for part in parts if part)


def _upsert_embeddings(entry: LorebookEntry) -> None:
    text = _compose_document(entry)
    if not text:
        return

    try:
        emb384 = embeddings.get_embedding_st(text)
        emb768 = embeddings.get_embedding_ollama(text)

        metadata = {
            "title": entry.title,
            "category": entry.category,
            "active": entry.active,
        }

        if emb384:
            vector_service.upsert_text(
                doc_id=str(entry.id),
                text=text,
                embedding=emb384,
                metadata={**metadata, "dimension": 384},
                collection_name=LOREBOOK_COLLECTION_384,
            )

        if emb768:
            vector_service.upsert_text(
                doc_id=str(entry.id),
                text=text,
                embedding=emb768,
                metadata={**metadata, "dimension": 768},
                collection_name=LOREBOOK_COLLECTION_768,
            )
    except Exception as exc:
        log_audit_entry(
            "lorebook_embedding_error",
            "[Lorebook] Failed to upsert embeddings",
            AuditStatus.ERROR,
            details={"entry_id": entry.id, "error": str(exc)},
        )


def _delete_embeddings(entry_id: int) -> None:
    try:
        vector_service.delete_text(str(entry_id), collection_name=LOREBOOK_COLLECTION_384)
        vector_service.delete_text(str(entry_id), collection_name=LOREBOOK_COLLECTION_768)
    except Exception as exc:
        log_audit_entry(
            "lorebook_delete_error",
            "[Lorebook] Failed to delete embeddings",
            AuditStatus.ERROR,
            details={"entry_id": entry_id, "error": str(exc)},
        )


# Public API -----------------------------------------------------------------


def get_entries() -> List[Dict[str, Any]]:
    session: Session = SessionLocal()
    try:
        entries = session.query(LorebookEntry).order_by(LorebookEntry.id.asc()).all()
        return [_entry_to_dict(entry) for entry in entries]
    finally:
        session.close()


def add_entry(payload: Dict[str, Any]) -> Dict[str, Any]:
    session: Session = SessionLocal()
    try:
        entry = LorebookEntry(
            title=payload.get("title") or "Untitled",
            content=payload.get("content", ""),
            keywords=payload.get("keywords", ""),
            category=payload.get("category", "general"),
            active=payload.get("active", True),
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)

        _upsert_embeddings(entry)
        return _entry_to_dict(entry)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def update_entry(entry_id: int, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    session: Session = SessionLocal()
    try:
        entry = session.query(LorebookEntry).filter_by(id=entry_id).first()
        if not entry:
            return None

        entry.title = payload.get("title", entry.title)
        entry.content = payload.get("content", entry.content)
        entry.keywords = payload.get("keywords", entry.keywords)
        entry.category = payload.get("category", entry.category)
        entry.active = payload.get("active", entry.active)

        session.commit()
        session.refresh(entry)

        _upsert_embeddings(entry)
        return _entry_to_dict(entry)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def delete_entry(entry_id: int) -> bool:
    session: Session = SessionLocal()
    try:
        entry = session.query(LorebookEntry).filter_by(id=entry_id).first()
        if not entry:
            return False

        session.delete(entry)
        session.commit()
        _delete_embeddings(entry_id)
        return True
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def search_entries(
    query: str,
    top_k: Optional[int] = None,
    min_similarity: Optional[float] = None,
    use_keyword_fallback: Optional[bool] = None,
) -> List[Dict[str, Any]]:
    session: Session = SessionLocal()
    try:
        if top_k is None:
            top_k = 5
        if min_similarity is None:
            min_similarity = 0.7
        if use_keyword_fallback is None:
            use_keyword_fallback = False

        if not query.strip():
            return get_entries()

        try:
            embedding_768 = embeddings.get_embedding_ollama(query)
            if embedding_768:
                results_768 = vector_service.search(
                    query_embedding=embedding_768,
                    top_k=top_k,
                    collection_name=LOREBOOK_COLLECTION_768,
                )
                matches = _process_search_results(session, results_768, min_similarity)
                if matches:
                    log_audit_entry(
                        "lorebook_vector_matches",
                        "[Lorebook] Vector matches retrieved (768-dim)",
                        AuditStatus.INFO,
                        details={
                            "query": query,
                            "matches": [
                                {"id": m.get("id"), "title": m.get("title"), "similarity": m.get("similarity")}
                                for m in matches
                            ],
                        },
                    )
                    return matches
        except Exception as exc:
            log_audit_entry(
                "lorebook_search_768_error",
                "[Lorebook] Search in 768 collection failed",
                AuditStatus.WARNING,
                details={"query": query, "error": str(exc)},
            )

        try:
            embedding_384 = embeddings.get_embedding_st(query)
            if embedding_384:
                results_384 = vector_service.search(
                    query_embedding=embedding_384,
                    top_k=top_k,
                    collection_name=LOREBOOK_COLLECTION_384,
                )
                matches = _process_search_results(session, results_384, min_similarity)
                if matches:
                    log_audit_entry(
                        "lorebook_vector_matches",
                        "[Lorebook] Vector matches retrieved (384-dim)",
                        AuditStatus.INFO,
                        details={
                            "query": query,
                            "matches": [
                                {"id": m.get("id"), "title": m.get("title"), "similarity": m.get("similarity")}
                                for m in matches
                            ],
                        },
                    )
                    return matches
        except Exception as exc:
            log_audit_entry(
                "lorebook_search_384_error",
                "[Lorebook] Search in 384 collection failed",
                AuditStatus.ERROR,
                details={"query": query, "error": str(exc)},
            )

        log_audit_entry(
            "lorebook_zero_matches",
            "[Lorebook] No vector matches found, using keyword fallback",
            AuditStatus.INFO,
            details={"query": query},
        )
        return _keyword_fallback(session, query, top_k) if use_keyword_fallback else []
    finally:
        session.close()


def _process_search_results(
    session: Session, results: Dict[str, Any], min_similarity: float
) -> List[Dict[str, Any]]:
    matches: List[Dict[str, Any]] = []
    ids = results.get("ids", [[]])[0]
    distances = results.get("distances", [[1.0]])[0]

    for doc_id, distance in zip(ids, distances):
        if doc_id is None:
            continue

        similarity = 1 - float(distance)
        if similarity < min_similarity:
            continue

        try:
            entry_id = int(doc_id)
        except (TypeError, ValueError):
            continue

        entry = session.query(LorebookEntry).filter_by(id=entry_id).first()
        if entry and entry.active:
            entry_dict = _entry_to_dict(entry)
            entry_dict["similarity"] = similarity
            matches.append(entry_dict)

    return matches


def _keyword_fallback(session: Session, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    query_lower = query.lower()
    tokens = set(filter(None, __tokenize(query_lower)))
    results: List[Dict[str, Any]] = []

    for entry in (
        session.query(LorebookEntry)
        .filter(LorebookEntry.active == True)  # noqa: E712
        .all()
    ):
        haystack = " ".join(
            filter(
                None,
                [entry.title, entry.content, entry.keywords, entry.category],
            )
        ).lower()
        entry_tokens = set(filter(None, __tokenize(haystack)))
        if query_lower in haystack or tokens & entry_tokens:
            results.append(_entry_to_dict(entry))
            if len(results) >= top_k:
                break

    return results


def __tokenize(text: str) -> List[str]:
    import re

    return re.findall(r"[\w\-]+", text)
