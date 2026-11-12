"""Map gold (filename, page, span) labels onto retrieved chunks at evaluation time.

A retrieved chunk is relevant if it overlaps a gold span: same filename (case-insensitive
basename match), same page, and character-overlap ratio above a threshold.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional, Sequence


def normalize_text(text: str) -> str:
    """Lowercase and collapse whitespace for stable overlap measurement."""
    return re.sub(r"\s+", " ", (text or "").strip().lower())


_UUID_PREFIX = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}_",
    re.IGNORECASE,
)


def basename_key(filename: str) -> str:
    """Normalize filename for matching gold ↔ retrieved metadata.

    Strips a leading UUID_ prefix used by DocuMind upload storage so that
    `evals/corpus/foo.pdf` labels match indexed `uploads/<uuid>_foo.pdf` metadata.
    """
    name = Path(filename or "").name.strip().lower()
    return _UUID_PREFIX.sub("", name)


def char_overlap_ratio(a: str, b: str) -> float:
    """
    Overlap ratio of two strings after normalization.

    Defined as |LCS| / max(len(a), len(b)) using a simple contiguous substring
    search: longest common substring length / max length. Returns 0 if either empty.
    """
    na = normalize_text(a)
    nb = normalize_text(b)
    if not na or not nb:
        return 0.0
    # Prefer containment: a gold span fully inside a chunk (or vice versa) is a hit.
    # Return 1.0 for full containment so short spans inside long chunks still match.
    if na in nb or nb in na:
        return 1.0
    # Longest common substring (O(n*m) — fine for chunk-sized strings)
    best = 0
    short, long_ = (na, nb) if len(na) <= len(nb) else (nb, na)
    for i in range(len(short)):
        for j in range(i + 1, len(short) + 1):
            sub = short[i:j]
            if len(sub) <= best:
                continue
            if sub in long_:
                best = len(sub)
    return best / max(len(na), len(nb))


@dataclass(frozen=True)
class GoldSpan:
    filename: str
    page: int
    span: str

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "GoldSpan":
        return cls(
            filename=str(d.get("filename") or ""),
            page=int(d.get("page") or 0),
            span=str(d.get("span") or ""),
        )


@dataclass(frozen=True)
class RetrievedChunk:
    filename: str
    page: int
    text: str
    chunk_id: str = ""

    @classmethod
    def from_langchain(cls, doc: Any, score: float = 0.0) -> "RetrievedChunk":
        meta = getattr(doc, "metadata", {}) or {}
        return cls(
            filename=str(meta.get("filename") or meta.get("source") or ""),
            page=int(meta.get("page_number") or meta.get("page") or 0),
            text=str(getattr(doc, "page_content", "") or ""),
            chunk_id=str(meta.get("chunk_id") or ""),
        )


def span_matches_chunk(
    gold: GoldSpan,
    chunk: RetrievedChunk,
    *,
    min_overlap: float = 0.5,
) -> bool:
    """True if gold span and chunk share file, page, and enough text overlap."""
    if basename_key(gold.filename) != basename_key(chunk.filename):
        return False
    if int(gold.page) != int(chunk.page):
        return False
    if not gold.span.strip():
        return False
    return char_overlap_ratio(gold.span, chunk.text) >= float(min_overlap)


def relevant_chunk_ids(
    gold_spans: Sequence[GoldSpan | dict[str, Any]],
    chunks: Sequence[RetrievedChunk | Any],
    *,
    min_overlap: float = 0.5,
) -> set[str]:
    """
    Return chunk_ids (or synthetic keys) that overlap any gold span.

    Accepts GoldSpan/dict and RetrievedChunk/LangChain Document.
    """
    spans = [
        g if isinstance(g, GoldSpan) else GoldSpan.from_dict(g) for g in gold_spans
    ]
    retrieved: list[RetrievedChunk] = []
    for c in chunks:
        if isinstance(c, RetrievedChunk):
            retrieved.append(c)
        elif isinstance(c, tuple) and len(c) >= 1:
            retrieved.append(RetrievedChunk.from_langchain(c[0]))
        else:
            retrieved.append(RetrievedChunk.from_langchain(c))

    hits: set[str] = set()
    for i, chunk in enumerate(retrieved):
        key = chunk.chunk_id or f"idx:{i}"
        for g in spans:
            if span_matches_chunk(g, chunk, min_overlap=min_overlap):
                hits.add(key)
                break
    return hits


def ranks_of_relevant(
    gold_spans: Sequence[GoldSpan | dict[str, Any]],
    ranked_chunks: Sequence[RetrievedChunk | Any],
    *,
    min_overlap: float = 0.5,
) -> list[int]:
    """1-based ranks of retrieved chunks that match any gold span (preserving order)."""
    spans = [
        g if isinstance(g, GoldSpan) else GoldSpan.from_dict(g) for g in gold_spans
    ]
    ranks: list[int] = []
    for i, c in enumerate(ranked_chunks, start=1):
        chunk = (
            c
            if isinstance(c, RetrievedChunk)
            else RetrievedChunk.from_langchain(c[0] if isinstance(c, tuple) else c)
        )
        if any(span_matches_chunk(g, chunk, min_overlap=min_overlap) for g in spans):
            ranks.append(i)
    return ranks
