"""FAISS vector store management with metadata tracking."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Optional

import faiss
import numpy as np
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document as LCDocument

from backend.app.config import get_settings
from backend.app.rag.llm_factory import get_shared_embeddings
from backend.app.utils.logging import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()
_store: FAISS | None = None


def _index_path() -> Path:
    return get_settings().vector_store_path / "faiss_index"


def _meta_path() -> Path:
    return get_settings().vector_store_path / "metadata.json"


def _load_metadata() -> dict[str, Any]:
    path = _meta_path()
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"chunks": {}, "doc_chunk_ids": {}}


def _save_metadata(meta: dict[str, Any]) -> None:
    path = _meta_path()
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _embedding_dim(embeddings=None) -> int:
    """Detect vector size from the live embedding model (never trust a stale config)."""
    embeddings = embeddings or get_shared_embeddings()
    try:
        sample = embeddings.embed_query("dimension probe")
        dim = len(sample)
        if dim > 0:
            return dim
    except Exception as exc:
        logger.warning("embedding_dim_probe_failed", error=str(exc))
    return get_settings().embedding_dimensions


def _empty_store() -> FAISS:
    embeddings = get_shared_embeddings()
    dim = _embedding_dim(embeddings)
    logger.info("faiss_empty_index", dimensions=dim)
    index = faiss.IndexFlatL2(dim)
    return FAISS(
        embedding_function=embeddings,
        index=index,
        docstore=InMemoryDocstore({}),
        index_to_docstore_id={},
    )


def reset_vector_store() -> None:
    """Drop in-memory + on-disk FAISS index (use after switching embedding models)."""
    global _store
    with _lock:
        _store = None
        path = _index_path()
        for name in ("index.faiss", "index.pkl"):
            fp = path / name
            if fp.exists():
                fp.unlink(missing_ok=True)
        meta = _meta_path()
        if meta.exists():
            meta.unlink(missing_ok=True)
        logger.info("faiss_reset")


def get_vector_store() -> FAISS:
    """Load or create the shared FAISS vector store."""
    global _store
    with _lock:
        if _store is not None:
            return _store
        path = _index_path()
        embeddings = get_shared_embeddings()
        expected_dim = _embedding_dim(embeddings)
        if (path / "index.faiss").exists():
            try:
                loaded = FAISS.load_local(
                    str(path),
                    embeddings,
                    allow_dangerous_deserialization=True,
                )
                if loaded.index.d != expected_dim:
                    logger.warning(
                        "faiss_dim_mismatch",
                        index_dim=loaded.index.d,
                        embedding_dim=expected_dim,
                    )
                    for name in ("index.faiss", "index.pkl"):
                        (path / name).unlink(missing_ok=True)
                else:
                    _store = loaded
                    logger.info("faiss_loaded", path=str(path), dimensions=expected_dim)
                    return _store
            except Exception as exc:
                logger.warning("faiss_load_failed", error=str(exc))
        _store = _empty_store()
        logger.info("faiss_created_empty", dimensions=expected_dim)
        return _store


def save_vector_store() -> None:
    """Persist the FAISS index to disk."""
    global _store
    with _lock:
        if _store is None:
            return
        path = _index_path()
        path.mkdir(parents=True, exist_ok=True)
        _store.save_local(str(path))
        logger.info("faiss_saved", path=str(path))


def add_documents(documents: list[LCDocument]) -> list[str]:
    """Embed and add documents to FAISS. Returns FAISS docstore IDs."""
    global _store
    if not documents:
        return []
    store = get_vector_store()
    with _lock:
        # Rebuild if index dim drifted from embedding model
        try:
            probe = store.embedding_function.embed_query("dim check")
            if store.index.d != len(probe):
                logger.warning(
                    "faiss_recreating_for_dim",
                    index_dim=store.index.d,
                    embedding_dim=len(probe),
                )
                _store = _empty_store()
                store = _store
        except Exception as exc:
            logger.warning("faiss_dim_check_failed", error=str(exc))
        ids = store.add_documents(documents)
        meta = _load_metadata()
        for doc_id, doc in zip(ids, documents):
            chunk_id = doc.metadata.get("chunk_id", doc_id)
            document_id = doc.metadata.get("document_id", "")
            meta["chunks"][chunk_id] = {
                "faiss_id": doc_id,
                "document_id": document_id,
                "filename": doc.metadata.get("filename"),
                "page_number": doc.metadata.get("page_number"),
                "chunk_index": doc.metadata.get("chunk_index"),
            }
            meta.setdefault("doc_chunk_ids", {}).setdefault(document_id, []).append(chunk_id)
        _save_metadata(meta)
    save_vector_store()
    return ids


def delete_document_vectors(document_id: str) -> int:
    """Remove all vectors belonging to a document. Returns count removed."""
    global _store
    store = get_vector_store()
    meta = _load_metadata()
    chunk_ids = meta.get("doc_chunk_ids", {}).get(document_id, [])
    if not chunk_ids:
        return 0

    faiss_ids = []
    for cid in chunk_ids:
        info = meta["chunks"].get(cid)
        if info and info.get("faiss_id"):
            faiss_ids.append(info["faiss_id"])

    with _lock:
        if faiss_ids:
            try:
                store.delete(faiss_ids)
            except Exception as exc:
                logger.warning("faiss_delete_partial", error=str(exc))
                # Rebuild without deleted docs as fallback
                _rebuild_without(document_id)

        for cid in chunk_ids:
            meta["chunks"].pop(cid, None)
        meta.get("doc_chunk_ids", {}).pop(document_id, None)
        _save_metadata(meta)

    save_vector_store()
    return len(chunk_ids)


def _rebuild_without(document_id: str) -> None:
    """Rebuild FAISS index excluding a document (fallback)."""
    global _store
    store = get_vector_store()
    remaining: list[LCDocument] = []
    for _id, doc in store.docstore._dict.items():  # type: ignore[attr-defined]
        if doc.metadata.get("document_id") != document_id:
            remaining.append(doc)
    _store = _empty_store()
    if remaining:
        _store.add_documents(remaining)
    logger.info("faiss_rebuilt", remaining=len(remaining))


def rebuild_from_documents(all_docs: list[LCDocument]) -> int:
    """Fully rebuild the FAISS index from a list of documents."""
    global _store
    with _lock:
        _store = _empty_store()
        meta: dict[str, Any] = {"chunks": {}, "doc_chunk_ids": {}}
        if all_docs:
            ids = _store.add_documents(all_docs)
            for doc_id, doc in zip(ids, all_docs):
                chunk_id = doc.metadata.get("chunk_id", doc_id)
                document_id = doc.metadata.get("document_id", "")
                meta["chunks"][chunk_id] = {
                    "faiss_id": doc_id,
                    "document_id": document_id,
                    "filename": doc.metadata.get("filename"),
                    "page_number": doc.metadata.get("page_number"),
                    "chunk_index": doc.metadata.get("chunk_index"),
                }
                meta.setdefault("doc_chunk_ids", {}).setdefault(document_id, []).append(chunk_id)
        _save_metadata(meta)
    save_vector_store()
    return len(all_docs)


def similarity_search(
    query: str,
    k: int = 4,
    document_ids: Optional[list[str]] = None,
) -> list[tuple[LCDocument, float]]:
    """Vector similarity search with optional metadata filtering."""
    store = get_vector_store()
    filter_dict = None
    if document_ids:
        # FAISS langchain filter: custom callable via fetch then filter
        results = store.similarity_search_with_score(query, k=k * 3)
        filtered = [
            (doc, float(score))
            for doc, score in results
            if doc.metadata.get("document_id") in document_ids
        ]
        return filtered[:k]

    results = store.similarity_search_with_score(query, k=k)
    # FAISS L2 distance: lower is better — convert to similarity-ish score
    return [(doc, float(score)) for doc, score in results]
