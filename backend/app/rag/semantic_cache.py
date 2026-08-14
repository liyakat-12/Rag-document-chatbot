"""Semantic cache for near-duplicate queries."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

import numpy as np
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.db.models import SemanticCacheEntry
from backend.app.rag.llm_factory import get_shared_embeddings
from backend.app.utils.logging import get_logger

logger = get_logger(__name__)

# In-memory counters for admin dashboard
_cache_hits = 0
_cache_misses = 0


def get_cache_stats() -> dict[str, int]:
    return {"cache_hits": _cache_hits, "cache_misses": _cache_misses}


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def _query_hash(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode()).hexdigest()


async def lookup_cache(
    session: AsyncSession,
    query: str,
) -> Optional[dict[str, Any]]:
    """Return a cached answer if a semantically similar query exists."""
    global _cache_hits, _cache_misses
    settings = get_settings()
    if not settings.semantic_cache_enabled:
        return None

    # Exact hash hit first
    qh = _query_hash(query)
    result = await session.execute(
        select(SemanticCacheEntry).where(SemanticCacheEntry.query_hash == qh)
    )
    entry = result.scalar_one_or_none()
    if entry:
        entry.hit_count += 1
        _cache_hits += 1
        logger.info("semantic_cache_exact_hit", query_hash=qh)
        return {
            "answer": entry.answer,
            "sources": json.loads(entry.sources_json),
            "confidence": entry.confidence,
            "cached": True,
        }

    # Semantic similarity against recent entries
    embeddings = get_shared_embeddings()
    query_vec = await embeddings.aembed_query(query)

    result = await session.execute(
        select(SemanticCacheEntry).order_by(SemanticCacheEntry.created_at.desc()).limit(100)
    )
    entries = result.scalars().all()
    best: SemanticCacheEntry | None = None
    best_sim = 0.0
    for e in entries:
        stored = json.loads(e.embedding_json)
        sim = _cosine_similarity(query_vec, stored)
        if sim > best_sim:
            best_sim = sim
            best = e

    if best and best_sim >= settings.semantic_cache_threshold:
        best.hit_count += 1
        _cache_hits += 1
        logger.info("semantic_cache_hit", similarity=best_sim)
        return {
            "answer": best.answer,
            "sources": json.loads(best.sources_json),
            "confidence": best.confidence,
            "cached": True,
        }

    _cache_misses += 1
    return None


async def store_cache(
    session: AsyncSession,
    query: str,
    answer: str,
    sources: list[dict[str, Any]],
    confidence: float,
) -> None:
    """Store a query/answer pair in the semantic cache."""
    settings = get_settings()
    if not settings.semantic_cache_enabled:
        return

    embeddings = get_shared_embeddings()
    query_vec = await embeddings.aembed_query(query)
    entry = SemanticCacheEntry(
        query_hash=_query_hash(query),
        query_text=query,
        embedding_json=json.dumps(query_vec),
        answer=answer,
        sources_json=json.dumps(sources),
        confidence=confidence,
    )
    session.add(entry)
    logger.info("semantic_cache_stored")
