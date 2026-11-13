"""Refusal / weak-evidence engine (Phase 2 code path; disabled by default).

Five signals per query → answered | weak_evidence | not_found.
All cutoffs live in Settings and are marked UNCALIBRATED placeholders.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal, Optional

from langchain_core.documents import Document as LCDocument

Decision = Literal["answered", "weak_evidence", "not_found"]

# Percentages / decimals that must survive punctuation stripping
# Note: do not use \b after '%' — '%' and whitespace are both non-word chars.
_PCT_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?%")
_NUM_RE = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.%])")
# Scheme / product codes like HDFC/O/E/MIF/07/04/0015 or INF0AUD00001
_CODE_RE = re.compile(r"\b[A-Z]{2,}(?:/[A-Z0-9.\-]+){1,}\b|\b[A-Z]{2,}\d[A-Z0-9\-]*\b", re.I)
# Critical proper-ish tokens: capitalized sequences, AMC/fund keywords
_PROPER_RE = re.compile(r"\b(?:[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}|[A-Z]{2,}(?:\s+[A-Z]{2,})*)\b")

_CRITICAL_HINTS = {
    "hdfc", "kotak", "motilal", "nippon", "ppfas", "parag", "parikh", "sebi",
    "amfi", "ter", "aum", "isin", "nav", "sid", "exit", "load", "benchmark",
}


@dataclass
class RefusalThresholds:
    """UNCALIBRATED placeholders — tune via evals/calibrate_refusal.py only."""

    # Rank agreement: fraction of FAISS top-k also in BM25 top-k
    min_rank_agreement: float = 0.25  # UNCALIBRATED
    # Raw FAISS similarity (L2→sim) of top hit
    min_faiss_similarity: float = 0.35  # UNCALIBRATED
    # Raw BM25 score of top hit
    min_bm25_score: float = 1.0  # UNCALIBRATED
    # Share of query content terms found in top evidence
    min_content_term_coverage: float = 0.30  # UNCALIBRATED
    # Share of critical terms found in top evidence
    min_critical_term_coverage: float = 0.40  # UNCALIBRATED
    # How many fused hits to inspect for coverage
    coverage_top_n: int = 4  # UNCALIBRATED
    # Decision: not_found if this many hard fails
    not_found_hard_fails: int = 3  # UNCALIBRATED
    # Decision: weak_evidence if this many soft fails (and not not_found)
    weak_evidence_soft_fails: int = 2  # UNCALIBRATED


@dataclass
class RefusalSignals:
    rank_agreement: float
    faiss_similarity: float
    bm25_score: float
    content_term_coverage: float
    critical_term_coverage: float
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d


@dataclass
class RefusalVerdict:
    decision: Decision
    reason: str
    signals: RefusalSignals
    thresholds_uncalibrated: bool = True


def normalize_for_coverage(text: str) -> list[str]:
    """Lowercase + strip punctuation, keeping percentages like 1% / 0.20% intact.

    Used ONLY for refusal coverage signals — not for BM25 tokenization.
    """
    if not text:
        return []
    # Protect percentages
    protected: dict[str, str] = {}
    out = text

    def _protect(match: re.Match[str], prefix: str) -> str:
        key = f"__{prefix}{len(protected)}__"
        protected[key] = match.group(0).lower()
        return key

    out = _PCT_RE.sub(lambda m: _protect(m, "PCT"), out)
    # Drop punctuation except placeholders / alphanumerics / % already protected
    # Keep placeholder keys case-stable (do not lower the whole string first).
    pieces: list[str] = []
    for part in re.split(r"(__PCT\d+__)", out):
        if part in protected:
            pieces.append(part)
        else:
            low = part.lower()
            low = re.sub(r"[^\w\s%_]", " ", low)
            pieces.append(low)
    out = "".join(pieces)
    tokens = [t for t in out.split() if t]
    restored: list[str] = []
    for t in tokens:
        restored.append(protected.get(t, t))
    return restored


def extract_content_terms(query: str) -> set[str]:
    toks = normalize_for_coverage(query)
    stop = {
        "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of",
        "is", "are", "was", "what", "which", "who", "how", "when", "where", "why",
        "does", "do", "did", "can", "with", "from", "that", "this",
    }
    return {t for t in toks if t not in stop and len(t) > 1}


def extract_critical_terms(query: str) -> set[str]:
    """Numbers, percentages, scheme codes, fund/AMC names, other proper nouns."""
    critical: set[str] = set()
    for m in _PCT_RE.finditer(query):
        critical.add(m.group(0).lower())
    for m in _NUM_RE.finditer(query):
        critical.add(m.group(0).lower())
    for m in _CODE_RE.finditer(query):
        critical.add(m.group(0).lower())
    for m in _PROPER_RE.finditer(query):
        critical.add(m.group(0).lower())
    for tok in normalize_for_coverage(query):
        if tok in _CRITICAL_HINTS or any(h in tok for h in ("fund", "scheme", "circular")):
            critical.add(tok)
    return critical


def _overlap(terms: set[str], haystack_tokens: set[str]) -> float:
    if not terms:
        return 1.0
    hits = sum(1 for t in terms if t in haystack_tokens)
    return hits / len(terms)


def compute_signals(
    query: str,
    *,
    faiss_ranked: list[tuple[LCDocument, float]],
    bm25_ranked: list[tuple[LCDocument, float]],
    fused_ranked: list[tuple[LCDocument, float]],
    thresholds: RefusalThresholds | None = None,
) -> RefusalSignals:
    thr = thresholds or RefusalThresholds()
    faiss_ids = [
        str(d.metadata.get("chunk_id") or id(d)) for d, _ in faiss_ranked[: thr.coverage_top_n]
    ]
    bm25_ids = {
        str(d.metadata.get("chunk_id") or id(d)) for d, _ in bm25_ranked[: thr.coverage_top_n]
    }
    if not faiss_ids:
        agreement = 0.0
    else:
        agreement = sum(1 for i in faiss_ids if i in bm25_ids) / len(faiss_ids)

    faiss_sim = float(faiss_ranked[0][1]) if faiss_ranked else 0.0
    bm25_sc = float(bm25_ranked[0][1]) if bm25_ranked else 0.0

    top = fused_ranked[: thr.coverage_top_n] or faiss_ranked[: thr.coverage_top_n] or bm25_ranked[: thr.coverage_top_n]
    blob = " ".join(d.page_content for d, _ in top)
    hay = set(normalize_for_coverage(blob))
    content_terms = extract_content_terms(query)
    critical_terms = extract_critical_terms(query)

    return RefusalSignals(
        rank_agreement=round(agreement, 4),
        faiss_similarity=round(faiss_sim, 4),
        bm25_score=round(bm25_sc, 4),
        content_term_coverage=round(_overlap(content_terms, hay), 4),
        critical_term_coverage=round(_overlap(critical_terms, hay), 4),
        details={
            "content_terms": sorted(content_terms)[:40],
            "critical_terms": sorted(critical_terms)[:40],
            "n_faiss": len(faiss_ranked),
            "n_bm25": len(bm25_ranked),
            "n_fused": len(fused_ranked),
            "thresholds_note": "UNCALIBRATED placeholders",
        },
    )


def decide(
    signals: RefusalSignals,
    thresholds: RefusalThresholds | None = None,
) -> RefusalVerdict:
    thr = thresholds or RefusalThresholds()
    hard = 0
    soft = 0
    reasons: list[str] = []

    checks = [
        ("rank_agreement", signals.rank_agreement, thr.min_rank_agreement, True),
        ("faiss_similarity", signals.faiss_similarity, thr.min_faiss_similarity, True),
        ("bm25_score", signals.bm25_score, thr.min_bm25_score, False),
        ("content_term_coverage", signals.content_term_coverage, thr.min_content_term_coverage, False),
        ("critical_term_coverage", signals.critical_term_coverage, thr.min_critical_term_coverage, True),
    ]
    for name, val, cutoff, is_hard in checks:
        if val < cutoff:
            reasons.append(f"{name}={val:.3f}<{cutoff} (UNCALIBRATED)")
            if is_hard:
                hard += 1
            else:
                soft += 1

    if hard >= thr.not_found_hard_fails or (hard + soft) >= thr.not_found_hard_fails + 1:
        return RefusalVerdict(
            decision="not_found",
            reason="; ".join(reasons) or "insufficient retrieval support",
            signals=signals,
        )
    if soft + hard >= thr.weak_evidence_soft_fails:
        return RefusalVerdict(
            decision="weak_evidence",
            reason="; ".join(reasons) or "partial retrieval support",
            signals=signals,
        )
    return RefusalVerdict(
        decision="answered",
        reason="signals above UNCALIBRATED cutoffs",
        signals=signals,
    )


def thresholds_from_settings(settings: Any) -> RefusalThresholds:
    return RefusalThresholds(
        min_rank_agreement=float(getattr(settings, "refusal_min_rank_agreement", 0.25)),
        min_faiss_similarity=float(getattr(settings, "refusal_min_faiss_similarity", 0.35)),
        min_bm25_score=float(getattr(settings, "refusal_min_bm25_score", 1.0)),
        min_content_term_coverage=float(getattr(settings, "refusal_min_content_term_coverage", 0.30)),
        min_critical_term_coverage=float(getattr(settings, "refusal_min_critical_term_coverage", 0.40)),
        coverage_top_n=int(getattr(settings, "refusal_coverage_top_n", 4)),
        not_found_hard_fails=int(getattr(settings, "refusal_not_found_hard_fails", 3)),
        weak_evidence_soft_fails=int(getattr(settings, "refusal_weak_evidence_soft_fails", 2)),
    )


def refusal_config_hash(settings: Any) -> str:
    """Stable hash of refusal-related settings for cache keying."""
    payload = {
        "enabled": bool(getattr(settings, "refusal_enabled", False)),
        "min_rank_agreement": float(getattr(settings, "refusal_min_rank_agreement", 0.25)),
        "min_faiss_similarity": float(getattr(settings, "refusal_min_faiss_similarity", 0.35)),
        "min_bm25_score": float(getattr(settings, "refusal_min_bm25_score", 1.0)),
        "min_content_term_coverage": float(getattr(settings, "refusal_min_content_term_coverage", 0.30)),
        "min_critical_term_coverage": float(getattr(settings, "refusal_min_critical_term_coverage", 0.40)),
        "coverage_top_n": int(getattr(settings, "refusal_coverage_top_n", 4)),
        "not_found_hard_fails": int(getattr(settings, "refusal_not_found_hard_fails", 3)),
        "weak_evidence_soft_fails": int(getattr(settings, "refusal_weak_evidence_soft_fails", 2)),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


WEAK_EVIDENCE_PREFIX = "Weak evidence: "
NOT_FOUND_RELATED_NOTE = (
    "\n\nPossibly related passages were retrieved but did not meet evidence thresholds."
)


def apply_refusal_to_answer(
    answer: str,
    verdict: RefusalVerdict,
    *,
    related_snippets: Optional[list[str]] = None,
) -> str:
    """Adjust user-facing answer text when refusal is enabled."""
    if verdict.decision == "answered":
        return answer
    if verdict.decision == "weak_evidence":
        label = f"{WEAK_EVIDENCE_PREFIX}{verdict.reason}."
        if answer and not answer.startswith(WEAK_EVIDENCE_PREFIX):
            return f"{label}\n\n{answer}"
        return label
    # not_found
    from backend.app.rag.qa_chain import NOT_FOUND_MESSAGE

    base = NOT_FOUND_MESSAGE + NOT_FOUND_RELATED_NOTE
    if related_snippets:
        joined = "\n".join(f"- {s[:240]}" for s in related_snippets[:3])
        return f"{base}\n\n{joined}"
    return base
