"""Hybrid search: BM25 + dense vector retrieval with RRF fusion.

Retrieval process
-----------------
1. Semantic retrieval (FAISS): finds chunks with similar embedding vectors.
2. Keyword retrieval (BM25): finds lexical / exact-term matches.
3. Fusion (Reciprocal Rank Fusion): combines both ranked lists so results
   that appear high in either (or both) lists rise to the top.

RRF improves recall for both paraphrased questions and exact keyword queries.
`HYBRID_SEARCH_WEIGHT` controls dense vs sparse contribution
(dense_weight = HYBRID_SEARCH_WEIGHT, sparse_weight = 1 - that value).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from langchain_core.documents import Document as LCDocument
from rank_bm25 import BM25Okapi

from backend.app.config import get_settings
from backend.app.rag.vector_store import get_vector_store, similarity_search
from backend.app.utils.logging import get_logger

logger = get_logger(__name__)

_bm25: BM25Okapi | None = None
_bm25_docs: list[LCDocument] = []
_bm25_tokens: list[list[str]] = []

# Default RRF smoothing constant (Cormack et al.)
RRF_K = 60


@dataclass
class HybridSearchResult:
    """Fused retrieval hits plus developer-facing retrieval diagnostics."""

    results: list[tuple[LCDocument, float]]
    details: dict[str, Any] = field(default_factory=dict)


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in text.split() if t.strip()]


def _doc_key(doc: LCDocument) -> str:
    return str(doc.metadata.get("chunk_id") or doc.page_content[:64])


def _summary_hits(ranked: list[tuple[LCDocument, float]], limit: int = 5) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for rank, (doc, score) in enumerate(ranked[:limit], start=1):
        out.append(
            {
                "rank": rank,
                "chunk_id": doc.metadata.get("chunk_id"),
                "filename": doc.metadata.get("filename"),
                "page_number": doc.metadata.get("page_number"),
                "score": round(float(score), 4),
            }
        )
    return out


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
    k: int = RRF_K,
    weights: list[float] | None = None,
) -> list[tuple[LCDocument, float]]:
    """
    Combine multiple ranked lists via Reciprocal Rank Fusion.

    score(d) = sum_i  weight_i / (k + rank_i(d))
    """
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    if len(weights) != len(ranked_lists):
        raise ValueError("weights length must match ranked_lists length")

    scores: dict[str, float] = {}
    docs: dict[str, LCDocument] = {}
    for list_weight, ranked in zip(weights, ranked_lists):
        for rank, (doc, _) in enumerate(ranked):
            key = _doc_key(doc)
            scores[key] = scores.get(key, 0.0) + float(list_weight) * (1.0 / (k + rank + 1))
            docs[key] = doc
    fused = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [(docs[key], score) for key, score in fused]


def hybrid_search_detailed(
    query: str,
    k: int | None = None,
    document_ids: Optional[list[str]] = None,
) -> HybridSearchResult:
    """Hybrid retrieval with timing and per-retriever diagnostics."""
    settings = get_settings()
    top_k = k or settings.retriever_top_k
    fetch_k = max(top_k * 2, 8)
    dense_w = float(settings.hybrid_search_weight)
    dense_w = min(1.0, max(0.0, dense_w))
    sparse_w = 1.0 - dense_w

    t0 = time.perf_counter()
    t_dense0 = time.perf_counter()
    dense = similarity_search(query, k=fetch_k, document_ids=document_ids)
    dense_ms = (time.perf_counter() - t_dense0) * 1000

    t_sparse0 = time.perf_counter()
    sparse = bm25_search(query, k=fetch_k, document_ids=document_ids)
    sparse_ms = (time.perf_counter() - t_sparse0) * 1000

    fused_raw = reciprocal_rank_fusion([dense, sparse], weights=[dense_w, sparse_w])
    results = fused_raw[:top_k]

    if results:
        max_score = max(s for _, s in results) or 1.0
        normalized = [(doc, score / max_score) for doc, score in results]
    else:
        normalized = []

    total_ms = (time.perf_counter() - t0) * 1000
    details: dict[str, Any] = {
        "strategy": "hybrid_rrf",
        "top_k": top_k,
        "fetch_k": fetch_k,
        "rrf_k": RRF_K,
        "dense_weight": dense_w,
        "sparse_weight": sparse_w,
        "latency_ms": round(total_ms, 2),
        "semantic": {
            "count": len(dense),
            "latency_ms": round(dense_ms, 2),
            "hits": _summary_hits(dense),
        },
        "bm25": {
            "count": len(sparse),
            "latency_ms": round(sparse_ms, 2),
            "hits": _summary_hits(sparse),
        },
        "fused": {
            "count": len(normalized),
            "hits": _summary_hits(normalized),
        },
    }
    logger.info(
        "hybrid_search",
        query_len=len(query),
        results=len(normalized),
        latency_ms=round(total_ms, 2),
        dense=len(dense),
        sparse=len(sparse),
    )
    return HybridSearchResult(results=normalized, details=details)


def hybrid_search(
    query: str,
    k: int | None = None,
    document_ids: Optional[list[str]] = None,
) -> list[tuple[LCDocument, float]]:
    """
    Hybrid retrieval: dense (FAISS) + sparse (BM25) fused with RRF.
    Scores are normalized to [0, 1] confidence-friendly values.
    """
    return hybrid_search_detailed(query, k=k, document_ids=document_ids).results
