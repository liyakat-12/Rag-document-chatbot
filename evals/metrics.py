"""Pure evaluation metrics — unit-tested on hand-made inputs. No I/O."""

from __future__ import annotations

from typing import Optional, Sequence


def recall_at_k(relevant_ranks: Sequence[int], k: int) -> float:
    """1.0 if any relevant item appears in ranks 1..k (1-based ranks), else 0.0."""
    if not relevant_ranks or k <= 0:
        return 0.0
    return 1.0 if any(1 <= int(r) <= k for r in relevant_ranks) else 0.0


def recall_at_1(relevant_ranks: Sequence[int]) -> float:
    return recall_at_k(relevant_ranks, 1)


def recall_at_4(relevant_ranks: Sequence[int]) -> float:
    return recall_at_k(relevant_ranks, 4)


def precision_at_k(relevant_ranks: Sequence[int], k: int) -> float:
    """Fraction of the top-k slots that are relevant (by 1-based rank)."""
    if k <= 0:
        return 0.0
    hits = sum(1 for r in relevant_ranks if 1 <= int(r) <= k)
    return hits / float(k)


def mrr(relevant_ranks: Sequence[int]) -> float:
    """Mean Reciprocal Rank for a single query (first relevant rank)."""
    if not relevant_ranks:
        return 0.0
    first = min(int(r) for r in relevant_ranks if int(r) >= 1)
    return 1.0 / float(first)


def hit_rate(hits: Sequence[bool]) -> Optional[float]:
    if not hits:
        return None
    return sum(1 for h in hits if h) / len(hits)


def cache_hit_rate(hits: int, misses: int) -> Optional[float]:
    total = int(hits) + int(misses)
    if total <= 0:
        return None
    return int(hits) / float(total)


def not_found_accuracy(pred_refused: Sequence[bool], gold_unanswerable: Sequence[bool]) -> Optional[float]:
    """Accuracy of refusal decisions vs gold unanswerable labels."""
    if not pred_refused or len(pred_refused) != len(gold_unanswerable):
        return None if not pred_refused else None
    if len(pred_refused) == 0:
        return None
    correct = sum(1 for p, g in zip(pred_refused, gold_unanswerable) if bool(p) == bool(g))
    return correct / len(pred_refused)


def refusal_precision(pred_refused: Sequence[bool], gold_unanswerable: Sequence[bool]) -> Optional[float]:
    """Of predicted refusals, how many were truly unanswerable."""
    tp = sum(1 for p, g in zip(pred_refused, gold_unanswerable) if p and g)
    fp = sum(1 for p, g in zip(pred_refused, gold_unanswerable) if p and not g)
    denom = tp + fp
    return None if denom == 0 else tp / denom


def refusal_recall(pred_refused: Sequence[bool], gold_unanswerable: Sequence[bool]) -> Optional[float]:
    """Of truly unanswerable questions, how many were refused."""
    tp = sum(1 for p, g in zip(pred_refused, gold_unanswerable) if p and g)
    fn = sum(1 for p, g in zip(pred_refused, gold_unanswerable) if (not p) and g)
    denom = tp + fn
    return None if denom == 0 else tp / denom


def false_refusal_rate(pred_refused: Sequence[bool], gold_unanswerable: Sequence[bool]) -> Optional[float]:
    """Of answerable questions, how many were refused (false refusals)."""
    answerable = [(p, g) for p, g in zip(pred_refused, gold_unanswerable) if not g]
    if not answerable:
        return None
    return sum(1 for p, _ in answerable if p) / len(answerable)


def key_fact_coverage(answer: str, key_facts: Sequence[str]) -> Optional[float]:
    """Share of key_facts found as case-insensitive substrings in the answer."""
    if not key_facts:
        return None
    text = (answer or "").lower()
    hits = sum(1 for f in key_facts if f and f.lower() in text)
    return hits / len(key_facts)


def citation_precision(pred_citations: Sequence[dict], gold_filename_pages: set[tuple[str, int]]) -> Optional[float]:
    """Of predicted citations, share matching gold (filename, page)."""
    from backend.app.rag.citations import citation_precision as _cp

    return _cp(list(pred_citations), gold_filename_pages)


def citation_recall(pred_citations: Sequence[dict], gold_filename_pages: set[tuple[str, int]]) -> Optional[float]:
    from backend.app.rag.citations import citation_recall as _cr

    return _cr(list(pred_citations), gold_filename_pages)


def valid_citation_share(valid: int, total: int) -> Optional[float]:
    from backend.app.rag.citations import valid_citation_share as _vcs

    return _vcs(valid, total)


def latency_summary(samples_ms: Sequence[float]) -> dict[str, Optional[float]]:
    xs = sorted(float(x) for x in samples_ms)
    if not xs:
        return {"count": 0, "p50_ms": None, "p95_ms": None, "avg_ms": None}

    def _pct(p: float) -> float:
        if len(xs) == 1:
            return xs[0]
        idx = min(len(xs) - 1, max(0, int(round((p / 100.0) * (len(xs) - 1)))))
        return xs[idx]

    return {
        "count": len(xs),
        "p50_ms": round(_pct(50), 2),
        "p95_ms": round(_pct(95), 2),
        "avg_ms": round(sum(xs) / len(xs), 2),
    }
