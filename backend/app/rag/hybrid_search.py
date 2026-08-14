"""Hybrid search: BM25 + dense vector retrieval with RRF fusion."""

from __future__ import annotations

from typing import Optional

from langchain_core.documents import Document as LCDocument
from rank_bm25 import BM25Okapi

from backend.app.config import get_settings
from backend.app.rag.vector_store import get_vector_store, similarity_search
from backend.app.utils.logging import get_logger

logger = get_logger(__name__)

_bm25: BM25Okapi | None = None
_bm25_docs: list[LCDocument] = []
_bm25_tokens: list[list[str]] = []


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in text.split() if t.strip()]


def rebuild_bm25_index() -> None:
    """Rebuild BM25 index from all documents currently in FAISS."""
    global _bm25, _bm25_docs, _bm25_tokens
    store = get_vector_store()
    docs = list(store.docstore._dict.values())  # type: ignore[attr-defined]
    _bm25_docs = docs
    _bm25_tokens = [_tokenize(d.page_content) for d in docs]
    _bm25 = BM25Okapi(_bm25_tokens) if _bm25_tokens else None
    logger.info("bm25_rebuilt", documents=len(docs))


def ensure_bm25() -> None:
    """Lazily initialize BM25 if empty."""
    global _bm25
    if _bm25 is None:
        rebuild_bm25_index()


def bm25_search(
    query: str,
    k: int = 4,
    document_ids: Optional[list[str]] = None,
) -> list[tuple[LCDocument, float]]:
    """Sparse BM25 retrieval."""
    ensure_bm25()
    if _bm25 is None or not _bm25_docs:
        return []
    scores = _bm25.get_scores(_tokenize(query))
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    results: list[tuple[LCDocument, float]] = []
    for idx, score in ranked:
        doc = _bm25_docs[idx]
        if document_ids and doc.metadata.get("document_id") not in document_ids:
            continue
        results.append((doc, float(score)))
        if len(results) >= k:
            break
    return results


def reciprocal_rank_fusion(
    ranked_lists: list[list[tuple[LCDocument, float]]],
    k: int = 60,
) -> list[tuple[LCDocument, float]]:
    """Combine multiple ranked lists via Reciprocal Rank Fusion."""
    scores: dict[str, float] = {}
    docs: dict[str, LCDocument] = {}
    for ranked in ranked_lists:
        for rank, (doc, _) in enumerate(ranked):
            key = doc.metadata.get("chunk_id") or doc.page_content[:64]
            scores[key] = scores.get(key, 0.0) + 1.0 / (k + rank + 1)
            docs[key] = doc
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(docs[key], score) for key, score in fused]


def hybrid_search(
    query: str,
    k: int | None = None,
    document_ids: Optional[list[str]] = None,
) -> list[tuple[LCDocument, float]]:
    """
    Hybrid retrieval: dense (FAISS) + sparse (BM25) fused with RRF.
    Scores are normalized to [0, 1] confidence-friendly values.
    """
    settings = get_settings()
    top_k = k or settings.retriever_top_k
    fetch_k = max(top_k * 2, 8)

    dense = similarity_search(query, k=fetch_k, document_ids=document_ids)
    sparse = bm25_search(query, k=fetch_k, document_ids=document_ids)

    fused = reciprocal_rank_fusion([dense, sparse])
    results = fused[:top_k]

    if not results:
        return []

    # Normalize RRF scores to 0-1
    max_score = max(s for _, s in results) or 1.0
    normalized = [(doc, score / max_score) for doc, score in results]
    logger.info("hybrid_search", query_len=len(query), results=len(normalized))
    return normalized
