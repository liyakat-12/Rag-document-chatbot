"""Semantic / exact cache for near-duplicate queries (scoped by document filter).

Speed notes
-----------
- Exact-hash hits use an in-process LRU first (no DB round-trip).
- Embedding for similarity search is OFF by default (`semantic_cache_similarity=false`)
  so cache store/lookup does not re-embed on every answer.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict
from typing import Any, Optional

import numpy as np
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.db.models import SemanticCacheEntry
from backend.app.rag.llm_factory import get_shared_embeddings
from backend.app.utils.logging import get_logger

logger = get_logger(__name__)

_cache_hits = 0
_cache_misses = 0

# Process-local exact cache: query_hash -> payload
_MEM_MAX = 256
_mem_lock = threading.Lock()
_mem: OrderedDict[str, dict[str, Any]] = OrderedDict()


def get_cache_stats() -> dict[str, int]:
    return {"cache_hits": _cache_hits, "cache_misses": _cache_misses}


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    va = np.array(a, dtype=np.float32)
    vb = np.array(b, dtype=np.float32)
    denom = float(np.linalg.norm(va) * np.linalg.norm(vb))
    if denom == 0:
        return 0.0
    return float(np.dot(va, vb) / denom)


def _scope_key(document_ids: Optional[list[str]]) -> str:
    if not document_ids:
        return "all"
    return ",".join(sorted({d for d in document_ids if d}))


def _mode_key() -> str:
    settings = get_settings()
    from backend.app.rag.refusal import refusal_config_hash
    from backend.app.rag.reranker import reranker_state_for_cache

    refusal_h = refusal_config_hash(settings)
    rerank_s = reranker_state_for_cache()
    bm25_tok = getattr(settings, "retrieval_bm25_tokenizer", "whitespace")
    multi_query = "{}:{}:{}".format(
        int(getattr(settings, "retrieval_multi_query_enabled", False)),
        getattr(settings, "retrieval_multi_query_max_variants", 3),
        getattr(settings, "retrieval_multi_query_candidate_multiplier", 4),
    )
    return (
        f"{settings.llm_provider}|{settings.embedding_provider}|{settings.openai_chat_model}"
        f"|refusal:{refusal_h}|rerank:{rerank_s}|bm25:{bm25_tok}|multiq:{multi_query}"
        f"|exboost:{int(getattr(settings, 'retrieval_exact_match_boost', False))}"
        f"|dedupe:{int(getattr(settings, 'retrieval_dedupe_near_duplicates', False))}"
        f"|citeval:{int(getattr(settings, 'citations_validate', False))}"
        f"|inj:{int(getattr(settings, 'llm_injection_guard', True))}"
    )


def _query_hash(text: str, document_ids: Optional[list[str]] = None) -> str:
    normalized = " ".join(text.strip().lower().split())
    payload = f"{_scope_key(document_ids)}||{_mode_key()}||{normalized}"
    return hashlib.sha256(payload.encode()).hexdigest()


def _sources_match_scope(sources: list[dict[str, Any]], document_ids: Optional[list[str]]) -> bool:
    if not document_ids:
        return True
    allowed = set(document_ids)
    if not sources:
        return False
    for src in sources:
        doc_id = str(src.get("document_id") or "")
        if doc_id and doc_id not in allowed:
            return False
    return True


def _mem_get(qh: str) -> Optional[dict[str, Any]]:
    with _mem_lock:
        if qh not in _mem:
            return None
        _mem.move_to_end(qh)
        return dict(_mem[qh])


def _mem_put(qh: str, payload: dict[str, Any]) -> None:
    with _mem_lock:
        _mem[qh] = payload
        _mem.move_to_end(qh)
        while len(_mem) > _MEM_MAX:
            _mem.popitem(last=False)


def _mem_clear() -> None:
    with _mem_lock:
        _mem.clear()


async def lookup_cache(
    session: AsyncSession,
    query: str,
    document_ids: Optional[list[str]] = None,
) -> Optional[dict[str, Any]]:
    """Return a cached answer if an exact (or optional semantic) match exists."""
    global _cache_hits, _cache_misses
    settings = get_settings()
    if not settings.semantic_cache_enabled:
        return None

    qh = _query_hash(query, document_ids)

    # 1) In-memory exact hit (fastest)
    mem = _mem_get(qh)
    if mem and _sources_match_scope(mem.get("sources") or [], document_ids):
        _cache_hits += 1
        logger.info("semantic_cache_memory_hit", scope=_scope_key(document_ids))
        return {**mem, "cached": True}

    # 2) DB exact hash
    result = await session.execute(
        select(SemanticCacheEntry).where(SemanticCacheEntry.query_hash == qh)
    )
    entry = result.scalar_one_or_none()
    if entry:
        sources = json.loads(entry.sources_json)
        if _sources_match_scope(sources, document_ids):
            entry.hit_count += 1
            _cache_hits += 1
            payload = {
                "answer": entry.answer,
                "sources": sources,
                "confidence": entry.confidence,
                "cached": True,
            }
            _mem_put(qh, payload)
            logger.info("semantic_cache_exact_hit", query_hash=qh, scope=_scope_key(document_ids))
            return payload

    # 3) Optional slow semantic scan (embeds query) — disabled by default
    if not settings.semantic_cache_similarity or document_ids:
        _cache_misses += 1
        return None

    embeddings = get_shared_embeddings()
    query_vec = await embeddings.aembed_query(query)
    result = await session.execute(
        select(SemanticCacheEntry).order_by(SemanticCacheEntry.created_at.desc()).limit(100)
    )
    entries = result.scalars().all()
    best: SemanticCacheEntry | None = None
    best_sim = 0.0
    for e in entries:
        try:
            stored = json.loads(e.embedding_json)
        except Exception:
            continue
        if not stored:
            continue
        sim = _cosine_similarity(query_vec, stored)
        if sim > best_sim:
            best_sim = sim
            best = e

    if best and best_sim >= settings.semantic_cache_threshold:
        sources = json.loads(best.sources_json)
        best.hit_count += 1
        _cache_hits += 1
        payload = {
            "answer": best.answer,
            "sources": sources,
            "confidence": best.confidence,
            "cached": True,
        }
        logger.info("semantic_cache_hit", similarity=best_sim)
        return payload

    _cache_misses += 1
    return None


async def store_cache(
    session: AsyncSession,
    query: str,
    answer: str,
    sources: list[dict[str, Any]],
    confidence: float,
    document_ids: Optional[list[str]] = None,
) -> None:
    """Store a query/answer pair. Skips embedding unless similarity mode is on."""
    settings = get_settings()
    if not settings.semantic_cache_enabled:
        return

    qh = _query_hash(query, document_ids)
    payload = {
        "answer": answer,
        "sources": sources,
        "confidence": confidence,
        "cached": True,
    }
    _mem_put(qh, payload)

    embedding_json = "[]"
    if settings.semantic_cache_similarity and not document_ids:
        embeddings = get_shared_embeddings()
        query_vec = await embeddings.aembed_query(query)
        embedding_json = json.dumps(query_vec)

    entry = SemanticCacheEntry(
        query_hash=qh,
        query_text=query,
        embedding_json=embedding_json,
        answer=answer,
        sources_json=json.dumps(sources),
        confidence=confidence,
    )
    session.add(entry)
    logger.info("semantic_cache_stored", scope=_scope_key(document_ids), mem=True)


async def clear_semantic_cache(session: AsyncSession) -> int:
    """Drop all semantic cache rows + memory."""
    global _cache_hits, _cache_misses
    result = await session.execute(delete(SemanticCacheEntry))
    deleted = int(result.rowcount or 0)
    _cache_hits = 0
    _cache_misses = 0
    _mem_clear()
    logger.info("semantic_cache_cleared", deleted=deleted)
    return deleted
