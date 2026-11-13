"""Optional cross-encoder reranker (disabled by default)."""

from __future__ import annotations

import threading
from typing import Any

from langchain_core.documents import Document as LCDocument

from backend.app.config import get_settings
from backend.app.utils.logging import get_logger

logger = get_logger(__name__)

_lock = threading.Lock()
_model = None
_model_name: str | None = None
_load_failed = False


def _load_model():
    global _model, _model_name, _load_failed
    settings = get_settings()
    name = getattr(settings, "retrieval_reranker_model", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    with _lock:
        if _load_failed:
            return None
        if _model is not None and _model_name == name:
            return _model
        try:
            from sentence_transformers import CrossEncoder

            _model = CrossEncoder(name)
            _model_name = name
            logger.info("reranker_loaded", model=name)
            return _model
        except Exception as exc:
            _load_failed = True
            logger.warning("reranker_load_failed", error=str(exc), model=name)
            return None


def rerank_candidates(
    query: str,
    candidates: list[tuple[LCDocument, float]],
) -> tuple[list[tuple[LCDocument, float]], dict[str, Any]]:
    """Rerank fused candidates. On failure, return original RRF order."""
    if not candidates:
        return [], {"enabled": True, "fallback": "empty"}
    model = _load_model()
    if model is None:
        return candidates, {
            "enabled": True,
            "fallback": "rrf_order",
            "warning": "cross-encoder unavailable; using RRF order",
        }
    pairs = [(query, doc.page_content) for doc, _ in candidates]
    try:
        scores = model.predict(pairs)
        rescored = sorted(
            zip(candidates, scores),
            key=lambda x: float(x[1]),
            reverse=True,
        )
        out = [(doc, float(sc)) for (doc, _), sc in rescored]
        return out, {
            "enabled": True,
            "fallback": None,
            "model": _model_name,
            "n": len(out),
        }
    except Exception as exc:
        logger.warning("reranker_predict_failed", error=str(exc))
        return candidates, {
            "enabled": True,
            "fallback": "rrf_order",
            "warning": str(exc),
        }


def reranker_state_for_cache() -> str:
    settings = get_settings()
    if not getattr(settings, "retrieval_reranker_enabled", False):
        return "off"
    return f"on|{getattr(settings, 'retrieval_reranker_model', '')}|{getattr(settings, 'retrieval_reranker_top_n', 16)}"
