"""Corpus / question difficulty diagnostics for the isolated eval index."""

from __future__ import annotations

import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from evals.corpus_util import CORPUS_DIR, list_corpus_files
from evals.eval_index import build_or_load_eval_index, search_eval_index
from evals.metrics import mrr, recall_at_4
from evals.runner import load_config
from evals.schema import Question, load_questions
from evals.span_map import GoldSpan, ranks_of_relevant

STOPWORDS = {
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for", "of", "as",
    "is", "are", "was", "were", "be", "been", "being", "by", "with", "from", "that",
    "this", "these", "those", "it", "its", "into", "about", "over", "under", "than",
    "then", "what", "which", "who", "whom", "how", "when", "where", "why", "does",
    "do", "did", "can", "could", "should", "would", "will", "may", "might", "must",
    "according", "listed", "named", "document", "pdf", "page",
}


def content_words(text: str) -> set[str]:
    toks = re.findall(r"[A-Za-z0-9][A-Za-z0-9\-_/%\.]*", (text or "").lower())
    return {t for t in toks if t not in STOPWORDS and len(t) > 1}


def query_span_overlap(query: str, spans: list[str]) -> float | None:
    """Share of query content words that appear in the concatenated gold spans."""
    q = content_words(query)
    if not q:
        return None
    span_words: set[str] = set()
    for s in spans:
        span_words |= content_words(s)
    if not span_words:
        return 0.0
    return len(q & span_words) / len(q)


def random_recall_at_4(n_chunks: int, n_relevant: int = 1) -> float:
    """Expected Recall@4 if ranks are uniform random (approx)."""
    if n_chunks <= 0:
        return 0.0
    r = max(1, n_relevant)
    k = 4
    if n_chunks <= k:
        return 1.0
    # P(miss all k) = C(N-R,k)/C(N,k) when N-R >= k
    if n_chunks - r < k:
        return 1.0
    # compute via products to avoid huge factorials
    miss = 1.0
    for i in range(k):
        miss *= (n_chunks - r - i) / (n_chunks - i)
    return 1.0 - miss


def _page_counts() -> tuple[int, int]:
    from backend.app.rag.ingest import load_pdf

    n_docs = 0
    n_pages = 0
    for pdf in list_corpus_files(CORPUS_DIR):
        if pdf.suffix.lower() != ".pdf":
            continue
        n_docs += 1
        n_pages += len(load_pdf(pdf))
    return n_docs, n_pages


def run_ablation_modes(
    index,
    questions: list[Question],
    *,
    top_k: int = 4,
    min_overlap: float = 0.5,
) -> dict[str, float | None]:
    """Recall@4 for hybrid, faiss_only, bm25_only on answerable questions."""
    from evals.eval_index import _dense_search, _sparse_search
    from backend.app.rag.hybrid_search import reciprocal_rank_fusion

    modes = {"hybrid": [], "faiss_only": [], "bm25_only": []}
    for q in questions:
        if not q.answerable:
            continue
        gold = [GoldSpan(g.filename, g.page, g.span) for g in q.gold]
        fetch = max(top_k * 2, 8)
        dense = [(d, s) for d, s in _dense_search(index, q.query, fetch) if s >= 0.22]
        sparse = [(d, s) for d, s in _sparse_search(index, q.query, fetch) if s > 0]

        fused = reciprocal_rank_fusion([dense, sparse], weights=[0.5, 0.5]) if (dense or sparse) else []
        hybrid = fused[:top_k]
        faiss_only = dense[:top_k]
        bm25_only = sparse[:top_k]

        for name, ranked in (
            ("hybrid", hybrid),
            ("faiss_only", faiss_only),
            ("bm25_only", bm25_only),
        ):
            ranks = ranks_of_relevant(gold, ranked, min_overlap=min_overlap)
            modes[name].append(recall_at_4(ranks))

    def avg(xs: list[float]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    return {k: avg(v) for k, v in modes.items()}


def diagnose(
    *,
    questions_path: Path | str | None = None,
    config_name: str = "default",
) -> dict[str, Any]:
    config = load_config(config_name)
    qpath = Path(questions_path or Path(__file__).parent / "data" / "questions.jsonl")
    questions = load_questions(qpath)
    index = build_or_load_eval_index(config)
    n_docs, n_pages = _page_counts()

    overlaps: list[tuple[Question, float]] = []
    by_cat: dict[str, list[float]] = defaultdict(list)
    for q in questions:
        if not q.answerable or not q.gold:
            continue
        ov = query_span_overlap(q.query, [g.span for g in q.gold])
        if ov is None:
            continue
        overlaps.append((q, ov))
        by_cat[q.category].append(ov)

    ablation = run_ablation_modes(
        index,
        questions,
        top_k=int(config.get("retriever_top_k", 4)),
        min_overlap=float(config.get("span_min_overlap", 0.5)),
    )

    mean_ov = sum(o for _, o in overlaps) / len(overlaps) if overlaps else None
    cat_means = {c: (sum(v) / len(v) if v else None) for c, v in sorted(by_cat.items())}

    return {
        "n_documents": n_docs,
        "n_pages": n_pages,
        "n_chunks": index.n_chunks,
        "corpus_hash": index.corpus_hash,
        "chunking_config_hash": index.chunking_config_hash,
        "n_questions": len(questions),
        "n_answerable_overlap": len(overlaps),
        "random_recall_at_4_1relevant": random_recall_at_4(index.n_chunks, 1),
        "mean_query_span_overlap": mean_ov,
        "overlap_by_category": cat_means,
        "per_question_overlap": [
            {"id": q.id, "category": q.category, "overlap": round(o, 4)} for q, o in overlaps
        ],
        "recall_at_4_ablation": ablation,
    }


def render_difficulty_md(diag: dict[str, Any], *, title: str = "Eval difficulty") -> str:
    lines = [
        f"# {title}",
        "",
        "Generated by `python -m evals.difficulty`. Numbers are from a real run on the",
        "isolated eval index — not portfolio headline claims (labels may be draft).",
        "",
        "## Corpus / index",
        "",
        f"- Documents: **{diag['n_documents']}**",
        f"- Pages: **{diag['n_pages']}**",
        f"- Chunks: **{diag['n_chunks']}**",
        f"- Corpus hash: `{diag['corpus_hash']}`",
        f"- Chunking config hash: `{diag['chunking_config_hash']}`",
        f"- Random-retrieval expected Recall@4 (1 relevant chunk): "
        f"**{diag['random_recall_at_4_1relevant']:.4f}**",
        "",
        "## Query ↔ gold span content-word overlap (answerable only)",
        "",
        f"- Mean overlap: **{(diag['mean_query_span_overlap'] if diag['mean_query_span_overlap'] is not None else float('nan')):.4f}**"
        if diag["mean_query_span_overlap"] is not None
        else "- Mean overlap: —",
        f"- Answerable questions scored: {diag['n_answerable_overlap']} / {diag['n_questions']}",
        "",
        "| Category | Mean overlap |",
        "|----------|--------------|",
    ]
    for cat, val in (diag.get("overlap_by_category") or {}).items():
        lines.append(f"| {cat} | {val:.4f} |" if val is not None else f"| {cat} | — |")

    ab = diag.get("recall_at_4_ablation") or {}
    lines += [
        "",
        "## Recall@4 by retriever (answerable, draft labels OK)",
        "",
        "| Mode | Recall@4 |",
        "|------|----------|",
        f"| hybrid_rrf | {_fmt(ab.get('hybrid'))} |",
        f"| faiss_only | {_fmt(ab.get('faiss_only'))} |",
        f"| bm25_only | {_fmt(ab.get('bm25_only'))} |",
        "",
        "## Per-question overlap",
        "",
        "| id | category | overlap |",
        "|----|----------|---------|",
    ]
    for row in diag.get("per_question_overlap") or []:
        lines.append(f"| {row['id']} | {row['category']} | {row['overlap']:.4f} |")
    lines.append("")
    return "\n".join(lines)


def _fmt(v: float | None) -> str:
    return "—" if v is None else f"{v:.4f}"


def main() -> int:
    import json

    diag = diagnose()
    out = Path(__file__).parent / "DIFFICULTY.md"
    out.write_text(render_difficulty_md(diag), encoding="utf-8")
    print(json.dumps({k: diag[k] for k in diag if k != "per_question_overlap"}, indent=2))
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
