"""In-process latency metrics for DocuMind (no document contents stored)."""

from __future__ import annotations

import threading
from collections import deque
from typing import Any

_lock = threading.Lock()
_MAX = 200

# Rolling samples in milliseconds
_retrieval: deque[float] = deque(maxlen=_MAX)
_generation: deque[float] = deque(maxlen=_MAX)
_total: deque[float] = deque(maxlen=_MAX)
_cache_lookup: deque[float] = deque(maxlen=_MAX)
_faiss: deque[float] = deque(maxlen=_MAX)
_bm25: deque[float] = deque(maxlen=_MAX)


def record_chat_timings(
    *,
    retrieval_ms: float | None = None,
    generation_ms: float | None = None,
    total_ms: float | None = None,
    cache_lookup_ms: float | None = None,
    faiss_ms: float | None = None,
    bm25_ms: float | None = None,
) -> None:
    with _lock:
        if retrieval_ms is not None:
            _retrieval.append(float(retrieval_ms))
        if generation_ms is not None:
            _generation.append(float(generation_ms))
        if total_ms is not None:
            _total.append(float(total_ms))
        if cache_lookup_ms is not None:
            _cache_lookup.append(float(cache_lookup_ms))
        if faiss_ms is not None:
            _faiss.append(float(faiss_ms))
        if bm25_ms is not None:
            _bm25.append(float(bm25_ms))


def _stats(samples: deque[float]) -> dict[str, Any]:
    vals = sorted(samples)
    n = len(vals)
    if n == 0:
        return {"count": 0, "avg_ms": None, "p50_ms": None, "p95_ms": None}
    avg = sum(vals) / n
    p50 = vals[n // 2]
    p95 = vals[min(n - 1, int(n * 0.95))]
    return {
        "count": n,
        "avg_ms": round(avg, 2),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
    }


def get_latency_stats() -> dict[str, Any]:
    with _lock:
        return {
            "window": _MAX,
            "total": _stats(_total),
            "retrieval": _stats(_retrieval),
            "generation": _stats(_generation),
            "cache_lookup": _stats(_cache_lookup),
            "faiss": _stats(_faiss),
            "bm25": _stats(_bm25),
            "note": (
                "Rolling in-process samples since last backend start. "
                "Not persisted across restarts. Does not store query text."
            ),
        }
