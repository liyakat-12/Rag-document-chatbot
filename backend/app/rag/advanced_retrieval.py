"""Advanced query rewriting and cross-encoder reranking utilities.

Query rewriting is deliberately conservative: the original question is always
retained as a retrieval query. Rewritten variants add recall without allowing a
rewrite model to silently change the user's intent.

The reranker is optional and lazy-loaded. When enabled it uses a local
SentenceTransformers CrossEncoder and falls back to the fused RRF ranking if
the model cannot be loaded or scored.
"""
from __future__ import annotations

import asyncio
import re
import time
import threading
from typing import Any

from langchain_core.documents import Document as LCDocument

from backend.app.config import get_settings
from backend.app.rag.llm_factory import get_chat_llm
from backend.app.utils.logging import get_logger

logger = get_logger(__name__)

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "could", "do",
    "does", "for", "from", "how", "i", "in", "is", "it", "me", "my", "of",
    "on", "or", "please", "the", "this", "to", "was", "what", "when",
    "where", "which", "who", "why", "with", "would", "you", "your",
}
_cross_encoder: Any = None
_cross_encoder_model_name: str | None = None
_cross_encoder_lock = threading.Lock()


def _clean_query(value: str) -> str:
    value = re.sub(r"\s+", " ", value or "").strip()
    return value[:1000]


def _parse_query_variants(raw: str, original: str, max_variants: int) -> list[str]:
    """Parse newline/bullet-separated LLM output and constrain it."""
    candidates = [original]
    if max_variants <= 1:
        return candidates
    for line in (raw or "").splitlines():
        item = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip().strip('"')
        item = _clean_query(item)
        if item and item.lower() not in {q.lower() for q in candidates}:
            candidates.append(item)
        if len(candidates) >= max_variants:
            break
    return candidates


def _extractive_query_variants(question: str, max_variants: int) -> list[str]:
    """No-LLM fallback: retain original and build a keyword-focused variant."""
    original = _clean_query(question)
    terms = [
        token for token in re.findall(r"[\w'-]+", original)
        if len(token) > 2 and token.lower() not in _STOPWORDS
    ]
    keyword_query = " ".join(dict.fromkeys(terms))
    variants = [original]
    if keyword_query and keyword_query.lower() != original.lower():
        variants.append(keyword_query)
    return variants[:max_variants]


async def rewrite_query(
    question: str,
    recent_history: str = "",
    max_variants: int | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Generate bounded query variants, falling back safely when offline."""
    settings = get_settings()
    original = _clean_query(question)
    limit = max(1, min(max_variants or settings.query_rewrite_max_variants, 4))
    if not settings.query_rewriting_enabled or not original:
        return [original] if original else [], {"enabled": False, "variants": 1, "latency_ms": 0.0}

    started = time.perf_counter()
    try:
        if settings.llm_provider == "extractive":
            raise RuntimeError("query rewriting requires a generative LLM")
        llm = get_chat_llm(streaming=False)
        prompt = (
            "Rewrite the user's information-seeking question into up to "
            f"{limit - 1} concise, standalone search queries. Preserve the exact intent, "
            "entities, constraints, and technical terms. Do not answer the question. "
            "Return one query per line without commentary. The original query will "
            "also be searched.\n\n"
            f"Recent conversation (for resolving references only):\n{recent_history or '(none)'}"
            f"\n\nOriginal question:\n{original}"
        )
        response = await llm.ainvoke(prompt)
        raw = response.content if isinstance(response.content, str) else str(response.content)
        variants = _parse_query_variants(raw, original, limit)
        method = "llm"
    except Exception as exc:
        logger.info("query_rewrite_fallback", reason=str(exc))
        variants = _extractive_query_variants(original, limit)
        method = "keyword_fallback"

    return variants, {
        "enabled": True,
        "method": method,
        "variants": len(variants),
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
    }


def _get_cross_encoder():
    """Lazy-load model once per process to avoid startup cost when disabled."""
    global _cross_encoder, _cross_encoder_model_name
    settings = get_settings()
    model_name = settings.reranker_model
    if _cross_encoder is not None and _cross_encoder_model_name == model_name:
        return _cross_encoder
    with _cross_encoder_lock:
        if _cross_encoder is not None and _cross_encoder_model_name == model_name:
            return _cross_encoder
        from sentence_transformers import CrossEncoder

        _cross_encoder = CrossEncoder(model_name, max_length=settings.reranker_max_length)
        _cross_encoder_model_name = model_name
        return _cross_encoder


def rerank_documents(
    query: str,
    candidates: list[tuple[LCDocument, float]],
    top_k: int | None = None,
) -> tuple[list[tuple[LCDocument, float]], dict[str, Any]]:
    """Rerank fused candidates using pairwise query/document relevance scores."""
    settings = get_settings()
    keep = top_k or settings.retriever_top_k
    if not settings.reranker_enabled or not candidates:
        return candidates[:keep], {
            "enabled": False,
            "candidate_count": len(candidates),
            "reranked_count": min(len(candidates), keep),
            "latency_ms": 0.0,
        }

    started = time.perf_counter()
    try:
        model = _get_cross_encoder()
        pairs = [(query, doc.page_content[: settings.reranker_max_length * 4]) for doc, _ in candidates]
        scores = model.predict(pairs, show_progress_bar=False)
        if hasattr(scores, "tolist"):
            scores = scores.tolist()
        scores = list(scores)
        scored = [
            (doc, float(score))
            for (doc, _), score in zip(candidates, scores)
        ]
        scored.sort(key=lambda item: item[1], reverse=True)
        selected = scored[:keep]
        method = "cross_encoder"
    except Exception as exc:
        # Retrieval must remain available even if the optional model is unavailable.
        logger.warning("reranker_fallback", error=str(exc))
        selected = candidates[:keep]
        method = "rrf_fallback"

    elapsed = (time.perf_counter() - started) * 1000
    return selected, {
        "enabled": True,
        "method": method,
        "model": settings.reranker_model,
        "candidate_count": len(candidates),
        "reranked_count": len(selected),
        "latency_ms": round(elapsed, 2),
    }


async def retrieve_advanced(
    question: str,
    document_ids: list[str] | None = None,
    recent_history: str = "",
):
    """Rewrite -> multi-query hybrid retrieval -> deduplicate -> rerank."""
    from backend.app.rag.hybrid_search import (
        hybrid_search_detailed,
        _doc_key,
        RRF_K,
        ensure_bm25,
    )

    variants, rewrite_details = await rewrite_query(question, recent_history=recent_history)
    if not variants:
        variants = [_clean_query(question)]

    # Build the shared sparse index once before concurrent query tasks begin.
    # Otherwise the first parallel BM25 calls can race to initialize it.
    await asyncio.to_thread(ensure_bm25)

    # Query variants are searched independently. Their fused rankings are
    # merged through RRF so one verbose rewrite cannot dominate by raw score.
    detailed_results = await asyncio.gather(*[
        asyncio.to_thread(
            hybrid_search_detailed,
            variant,
            k=max(get_settings().retriever_top_k * get_settings().reranker_candidate_multiplier, 8),
            document_ids=document_ids,
        )
        for variant in variants
    ])
    merged: dict[str, tuple[LCDocument, float]] = {}
    variant_rankings = [result.results for result in detailed_results]
    for rank, ranked in enumerate(variant_rankings):
        weight = 1.0 if rank == 0 else 0.8
        for position, (doc, _) in enumerate(ranked, start=1):
            key = _doc_key(doc)
            prior = merged.get(key)
            score = (prior[1] if prior else 0.0) + weight / (RRF_K + position)
            merged[key] = (doc, score)

    candidates = sorted(merged.values(), key=lambda item: item[1], reverse=True)
    candidate_count = len(candidates)
    reranked, rerank_details = await asyncio.to_thread(
        rerank_documents, question, candidates, get_settings().retriever_top_k
    )

    # Scores are display heuristics, not calibrated relevance probabilities.
    # Keep the range comparable across reranker and safe RRF-fallback modes.
    if reranked and rerank_details.get("method") == "cross_encoder":
        values = [score for _, score in reranked]
        low, high = min(values), max(values)
        if high > low:
            reranked = [(doc, (score - low) / (high - low)) for doc, score in reranked]
        else:
            reranked = [(doc, 1.0) for doc, _ in reranked]
    elif reranked:
        max_score = max((score for _, score in reranked), default=0.0) or 1.0
        reranked = [(doc, score / max_score) for doc, score in reranked]

    from backend.app.rag.hybrid_search import HybridSearchResult
    details = {
        "strategy": "advanced_hybrid_rrf_rerank",
        "query_rewriting": rewrite_details,
        "query_variants": variants,
        "candidate_count": candidate_count,
        "reranking": rerank_details,
        "variant_retrieval": [
            {"query": variant, **result.details}
            for variant, result in zip(variants, detailed_results)
        ],
    }
    return HybridSearchResult(results=reranked, details=details)
