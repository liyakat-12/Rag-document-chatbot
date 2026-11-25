"""Near-duplicate chunk dedupe for the final evidence set (flagged off by default)."""

from __future__ import annotations

import re

from langchain_core.documents import Document as LCDocument


def _norm(text: str) -> str:
    t = (text or "").lower()
    t = re.sub(r"\s+", " ", t).strip()
    return t[:500]


def dedupe_near_duplicates(
    ranked: list[tuple[LCDocument, float]],
    *,
    jaccard_threshold: float = 0.85,
) -> list[tuple[LCDocument, float]]:
    """Drop later chunks that heavily overlap earlier ones (token Jaccard)."""
    kept: list[tuple[LCDocument, float]] = []
    kept_token_sets: list[set[str]] = []
    for doc, score in ranked:
        toks = set(_norm(doc.page_content).split())
        if not toks:
            kept.append((doc, score))
            kept_token_sets.append(toks)
            continue
        dup = False
        for prev in kept_token_sets:
            if not prev:
                continue
            inter = len(toks & prev)
            union = len(toks | prev) or 1
            if inter / union >= jaccard_threshold:
                dup = True
                break
        if not dup:
            kept.append((doc, score))
            kept_token_sets.append(toks)
    return kept
