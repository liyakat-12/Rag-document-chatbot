"""Optional LLM-assisted multi-query rewriting for document retrieval.

The original question is always retained. Rewrites are bounded and used only
to improve candidate recall; final answer generation still uses the user's
question and retrieved document context.
"""
from __future__ import annotations

import re
import time
from typing import Any

from backend.app.config import get_settings
from backend.app.rag.llm_factory import get_chat_llm
from backend.app.utils.logging import get_logger

logger = get_logger(__name__)

_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "could", "did",
    "do", "does", "for", "from", "had", "has", "have", "how", "i", "if",
    "in", "is", "it", "its", "me", "my", "of", "on", "or", "please", "the",
    "their", "them", "this", "to", "was", "what", "when", "where", "which",
    "who", "why", "with", "would", "you", "your",
}


def _clean_query(value: str) -> str:
    """Normalise whitespace and keep each search string bounded."""
    return re.sub(r"\s+", " ", (value or "")).strip()[:1000]


def parse_query_variants(raw: str, original: str, max_variants: int = 3) -> list[str]:
    """Parse one-query-per-line model output, retaining and deduplicating original."""
    original = _clean_query(original)
    variants = [original] if original else []
    if max_variants <= 1:
        return variants[:max_variants]

    for line in (raw or "").splitlines():
        candidate = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
        candidate = _clean_query(candidate.strip('"').strip("'"))
        if candidate and candidate.casefold() not in {item.casefold() for item in variants}:
            variants.append(candidate)
        if len(variants) >= max_variants:
            break
    return variants


def keyword_query_variant(question: str) -> str:
    """Build a conservative offline search variant by removing common stopwords."""
    terms = re.findall(r"[\w./%-]+", _clean_query(question))
    useful = [term for term in terms if len(term) > 2 and term.casefold() not in _STOPWORDS]
    return " ".join(dict.fromkeys(useful))


def _response_text(response: Any) -> str:
    content = getattr(response, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        pieces = []
        for block in content:
            if isinstance(block, dict):
                pieces.append(str(block.get("text") or ""))
            else:
                pieces.append(str(block))
        return "\n".join(pieces)
    return str(content or "")


async def generate_query_variants(
    question: str,
    recent_history: str = "",
    max_variants: int | None = None,
) -> tuple[list[str], dict[str, Any]]:
    """Return original + bounded alternate queries, using an offline fallback."""
    settings = get_settings()
    original = _clean_query(question)
    limit = max(1, min(int(max_variants or settings.retrieval_multi_query_max_variants), 4))
    if not original:
        return [], {"enabled": True, "method": "empty_query", "variants": 0, "latency_ms": 0.0}
    if limit == 1:
        return [original], {"enabled": True, "method": "original_only", "variants": 1, "latency_ms": 0.0}

    started = time.perf_counter()
    method = "keyword_fallback"
    variants: list[str]
    try:
        if settings.llm_provider == "extractive":
            raise RuntimeError("extractive mode does not provide generative query rewriting")
        llm = get_chat_llm(streaming=False)
        prompt = (
            "Create up to " + str(limit - 1) + " alternative search queries for a document "
            "retrieval system. Preserve the exact user intent, named entities, numbers, "
            "identifiers, quoted phrases, and constraints. Rephrase or make implicit "
            "concepts explicit; do not answer the question and do not invent details. "
            "Use recent conversation only to resolve references. Return one standalone "
            "query per line with no explanation. The original query will also be searched.\n\n"
            "Recent conversation:\n" + (recent_history[-2500:] or "(none)") +
            "\n\nOriginal question:\n" + original
        )
        response = await llm.ainvoke(prompt)
        variants = parse_query_variants(_response_text(response), original, limit)
        method = "llm"
    except Exception as exc:
        logger.info("multi_query_rewrite_fallback", reason=str(exc))
        variants = [original]
        fallback = keyword_query_variant(original)
        if fallback and fallback.casefold() != original.casefold():
            variants.append(fallback)
        variants = variants[:limit]

    return variants, {
        "enabled": True,
        "method": method,
        "variants": len(variants),
        "latency_ms": round((time.perf_counter() - started) * 1000, 2),
    }
