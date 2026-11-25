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
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from typing import Any, Optional

from langchain_core.documents import Document as LCDocument
from rank_bm25 import BM25Okapi

from backend.app.config import get_settings
from backend.app.rag.vector_store import get_vector_store, similarity_search
from backend.app.utils.logging import get_logger
from backend.app.utils.metrics import record_chat_timings

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
    # Pre-fusion lists (for refusal / ablations; not serialized to clients by default)
    dense_results: list[tuple[LCDocument, float]] = field(default_factory=list)
    sparse_results: list[tuple[LCDocument, float]] = field(default_factory=list)


def _tokenize_whitespace(text: str) -> list[str]:
    """Historical BM25 tokenizer (default). Do not change behaviour lightly."""
    return [t.lower() for t in text.split() if t.strip()]


def _tokenize_normalized(text: str) -> list[str]:
    """Optional BM25 tokenizer: lowercase, strip punctuation, keep % and codes."""
    from backend.app.rag.refusal import normalize_for_coverage

    return normalize_for_coverage(text)


def _tokenize(text: str) -> list[str]:
    settings = get_settings()
    mode = getattr(settings, "retrieval_bm25_tokenizer", "whitespace")
    if mode == "normalized":
        return _tokenize_normalized(text)
    return _tokenize_whitespace(text)


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
    *,
    dense_list_index: int = 0,
) -> list[tuple[LCDocument, float]]:
    """
    Combine multiple ranked lists via Reciprocal Rank Fusion.

    score(d) = sum_i  weight_i / (k + rank_i(d))

    Near-ties are broken deterministically by:
    (1) fused RRF score desc, (2) FAISS/dense raw score desc, (3) chunk_id asc.
    ``dense_list_index`` selects which input list supplies the FAISS score
    (default 0 = first list, matching hybrid_search call order).
    """
    if weights is None:
        weights = [1.0] * len(ranked_lists)
    if len(weights) != len(ranked_lists):
        raise ValueError("weights length must match ranked_lists length")

    scores: dict[str, float] = {}
    dense_scores: dict[str, float] = {}
    docs: dict[str, LCDocument] = {}
    for li, (list_weight, ranked) in enumerate(zip(weights, ranked_lists)):
        for rank, (doc, raw_score) in enumerate(ranked):
            key = _doc_key(doc)
            scores[key] = scores.get(key, 0.0) + float(list_weight) * (1.0 / (k + rank + 1))
            docs[key] = doc
            if li == dense_list_index:
                # Keep the best dense score if a doc appears once
                dense_scores[key] = max(dense_scores.get(key, float("-inf")), float(raw_score))
    fused = sorted(
        scores.items(),
        key=lambda item: (
            -item[1],
            -dense_scores.get(item[0], 0.0),
            item[0],
        ),
    )
    return [(docs[key], score) for key, score in fused]


def hybrid_search_detailed(
    query: str,
    k: int | None = None,
    document_ids: Optional[list[str]] = None,
    *,
    apply_reranker: bool = True,
    apply_dedupe: bool = True,
    record_metrics: bool = True,
) -> HybridSearchResult:
    """Hybrid retrieval with timing and per-retriever diagnostics."""
    settings = get_settings()
    top_k = k or settings.retriever_top_k
    fetch_k = max(top_k * 2, 8)
    dense_w = float(settings.hybrid_search_weight)
    dense_w = min(1.0, max(0.0, dense_w))
    sparse_w = 1.0 - dense_w

    t0 = time.perf_counter()

    # Run FAISS + BM25 concurrently — both are CPU-bound sync calls
    dense_ms = 0.0
    sparse_ms = 0.0

    def _dense() -> list[tuple[LCDocument, float]]:
        nonlocal dense_ms
        t = time.perf_counter()
        out = similarity_search(query, k=fetch_k, document_ids=document_ids)
        dense_ms = (time.perf_counter() - t) * 1000
        return out

    def _sparse() -> list[tuple[LCDocument, float]]:
        nonlocal sparse_ms
        t = time.perf_counter()
        out = bm25_search(query, k=fetch_k, document_ids=document_ids)
        sparse_ms = (time.perf_counter() - t) * 1000
        return out

    with ThreadPoolExecutor(max_workers=2, thread_name_prefix="hybrid") as pool:
        f_dense = pool.submit(_dense)
        f_sparse = pool.submit(_sparse)
        dense = f_dense.result()
        sparse = f_sparse.result()

    # Drop obviously irrelevant hits (no lexical overlap + weak semantic match)
    dense = [(d, s) for d, s in dense if s >= 0.22]
    sparse = [(d, s) for d, s in sparse if s > 0.0]
    if not dense and not sparse:
        total_ms = (time.perf_counter() - t0) * 1000
        if record_metrics:
            record_chat_timings(retrieval_ms=total_ms, faiss_ms=dense_ms, bm25_ms=sparse_ms)
        return HybridSearchResult(
            results=[],
            dense_results=[],
            sparse_results=[],
            details={
                "strategy": "hybrid_rrf",
                "parallel": True,
                "top_k": top_k,
                "fetch_k": fetch_k,
                "rrf_k": RRF_K,
                "dense_weight": dense_w,
                "sparse_weight": sparse_w,
                "latency_ms": round(total_ms, 2),
                "semantic": {"count": 0, "latency_ms": round(dense_ms, 2), "hits": []},
                "bm25": {"count": 0, "latency_ms": round(sparse_ms, 2), "hits": []},
                "fused": {"count": 0, "hits": []},
                "empty_reason": "no_relevant_hits",
            },
        )

    fused_raw = reciprocal_rank_fusion([dense, sparse], weights=[dense_w, sparse_w])
    if getattr(settings, "retrieval_exact_match_boost", False):
        fused_raw = _exact_match_boost(query, fused_raw)

    # Keep a wider candidate pool when optional rerank/dedupe flags are on
    pool_limit = top_k
    reranker_enabled = apply_reranker and getattr(settings, "retrieval_reranker_enabled", False)
    dedupe_enabled = apply_dedupe and getattr(settings, "retrieval_dedupe_near_duplicates", False)
    if reranker_enabled or dedupe_enabled:
        pool_limit = max(top_k * 3, int(getattr(settings, "retrieval_reranker_top_n", 16)))

    seen: set[str] = set()
    deduped: list[tuple[LCDocument, float]] = []
    for doc, score in fused_raw:
        key = _doc_key(doc)
        if key in seen:
            continue
        seen.add(key)
        deduped.append((doc, score))
        if len(deduped) >= pool_limit:
            break

    rerank_ms = 0.0
    rr_info: dict[str, Any] = {"enabled": False}
    if reranker_enabled and deduped:
        from backend.app.rag.reranker import rerank_candidates

        n = int(getattr(settings, "retrieval_reranker_top_n", 16))
        t_rr = time.perf_counter()
        deduped, rr_info = rerank_candidates(query, deduped[:n])
        rerank_ms = (time.perf_counter() - t_rr) * 1000

    if dedupe_enabled:
        from backend.app.rag.dedupe import dedupe_near_duplicates

        deduped = dedupe_near_duplicates(deduped)

    results = deduped[:top_k]

    if results:
        max_score = max(s for _, s in results) or 1.0
        normalized = [(doc, score / max_score) for doc, score in results]
    else:
        normalized = []

    total_ms = (time.perf_counter() - t0) * 1000
    if record_metrics:
        record_chat_timings(retrieval_ms=total_ms, faiss_ms=dense_ms, bm25_ms=sparse_ms)
    details: dict[str, Any] = {
        "strategy": "hybrid_rrf",
        "parallel": True,
        "top_k": top_k,
        "fetch_k": fetch_k,
        "rrf_k": RRF_K,
        "dense_weight": dense_w,
        "sparse_weight": sparse_w,
        "bm25_tokenizer": getattr(settings, "retrieval_bm25_tokenizer", "whitespace"),
        "latency_ms": round(total_ms, 2),
        "reranker_ms": round(rerank_ms, 2),
        "reranker": rr_info,
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
        parallel=True,
    )
    return HybridSearchResult(
        results=normalized,
        details=details,
        dense_results=dense,
        sparse_results=sparse,
    )


def _exact_match_boost(
    query: str,
    ranked: list[tuple[LCDocument, float]],
) -> list[tuple[LCDocument, float]]:
    """Boost chunks that contain codes, numbers, or quoted phrases from the query."""
    import re

    quotes = re.findall(r"\"([^\"]+)\"|'([^']+)'", query)
    phrases = [a or b for a, b in quotes]
    codes = re.findall(r"\b[A-Z]{2,}(?:/[A-Z0-9.\-]+)+\b", query, flags=re.I)
    nums = re.findall(r"\b\d+(?:\.\d+)?%?\b", query)
    needles = [p for p in phrases + codes + nums if p]
    if not needles:
        return ranked
    boosted: list[tuple[LCDocument, float]] = []
    for doc, score in ranked:
        text = (doc.page_content or "").lower()
        hit = sum(1 for n in needles if n.lower() in text)
        boosted.append((doc, score * (1.0 + 0.15 * hit)))
    boosted.sort(key=lambda x: x[1], reverse=True)
    return boosted


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
