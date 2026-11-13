"""Corpus / question difficulty diagnostics for the isolated primary eval index."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from evals.corpus_util import REAL_DIR, list_corpus_files
from evals.eval_index import (
    _dense_search,
    _sparse_search,
    _tokenize,
    build_or_load_eval_index,
)
from evals.metrics import recall_at_4
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
    if n_chunks - r < k:
        return 1.0
    miss = 1.0
    for i in range(k):
        miss *= (n_chunks - r - i) / (n_chunks - i)
    return 1.0 - miss


def _page_counts() -> tuple[int, int]:
    from backend.app.rag.ingest import load_pdf

    n_docs = 0
    n_pages = 0
    for pdf in list_corpus_files(subset="primary"):
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
) -> dict[str, Any]:
    """Recall@4 for hybrid / faiss_only / bm25_only overall and by category."""
    from backend.app.rag.hybrid_search import reciprocal_rank_fusion

    modes: dict[str, list[float]] = {"hybrid": [], "faiss_only": [], "bm25_only": []}
    by_cat: dict[str, dict[str, list[float]]] = defaultdict(
        lambda: {"hybrid": [], "faiss_only": [], "bm25_only": []}
    )
    bm25_misses: list[dict[str, Any]] = []

    for q in questions:
        if not q.answerable:
            continue
        gold = [GoldSpan(g.filename, g.page, g.span) for g in q.gold]
        fetch = max(top_k * 2, 8)
        dense = [(d, s) for d, s in _dense_search(index, q.query, fetch) if s >= 0.22]
        sparse = [(d, s) for d, s in _sparse_search(index, q.query, fetch) if s > 0]

        fused = (
            reciprocal_rank_fusion([dense, sparse], weights=[0.5, 0.5])
            if (dense or sparse)
            else []
        )
        hybrid = fused[:top_k]
        faiss_only = dense[:top_k]
        bm25_only = sparse[:top_k]

        for name, ranked in (
            ("hybrid", hybrid),
            ("faiss_only", faiss_only),
            ("bm25_only", bm25_only),
        ):
            ranks = ranks_of_relevant(gold, ranked, min_overlap=min_overlap)
            r4 = recall_at_4(ranks)
            modes[name].append(r4)
            by_cat[q.category][name].append(r4)

        bm25_ranks = ranks_of_relevant(gold, bm25_only, min_overlap=min_overlap)
        if not bm25_ranks and gold:
            # Locate a gold-overlapping chunk in the index for token comparison
            gold_chunk_tokens: list[str] = []
            for doc in index.bm25_docs:
                ranks_one = ranks_of_relevant(gold, [(doc, 1.0)], min_overlap=min_overlap)
                if ranks_one:
                    gold_chunk_tokens = _tokenize(doc.page_content)
                    break
            bm25_misses.append(
                {
                    "id": q.id,
                    "category": q.category,
                    "query": q.query,
                    "query_tokens": _tokenize(q.query),
                    "gold_chunk_tokens_sample": gold_chunk_tokens[:80],
                    "gold_filenames": [g.filename for g in q.gold],
                }
            )

    def avg(xs: list[float]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    overall = {k: avg(v) for k, v in modes.items()}
    by_category = {
        cat: {mode: avg(vals) for mode, vals in modes_d.items()}
        for cat, modes_d in sorted(by_cat.items())
    }
    by_category_n = {
        cat: len(modes_d["hybrid"]) for cat, modes_d in sorted(by_cat.items())
    }
    return {
        "overall": overall,
        "by_category": by_category,
        "by_category_n": by_category_n,
        "bm25_miss_examples": bm25_misses[:5],
        "hybrid_vs_faiss_gap": (
            None
            if overall.get("hybrid") is None or overall.get("faiss_only") is None
            else round(float(overall["hybrid"]) - float(overall["faiss_only"]), 4)
        ),
    }


def ingest_audit_real(config: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Per-document extraction/chunking audit for Phase 3 notes (no code changes)."""
    from backend.app.config import get_settings
    from backend.app.rag.ingest import load_pdf, split_documents

    settings = get_settings()
    chunk_size = int((config or {}).get("chunk_size", settings.chunk_size))
    chunk_overlap = int((config or {}).get("chunk_overlap", settings.chunk_overlap))
    old_size, old_overlap = settings.chunk_size, settings.chunk_overlap
    reports: list[dict[str, Any]] = []
    try:
        settings.chunk_size = chunk_size
        settings.chunk_overlap = chunk_overlap
        for pdf in list_corpus_files(subset="primary"):
            if pdf.suffix.lower() != ".pdf":
                continue
            pages = load_pdf(pdf)
            chunks = split_documents(pages, document_id="audit", filename=pdf.name)
            chars_per_page: list[tuple[int, int, int]] = []
            chunk_pages = Counter(
                int(c.metadata.get("page", -1)) + 1
                if isinstance(c.metadata.get("page"), int)
                else -1
                for c in chunks
            )
            # Prefer 1-indexed enumerate aligned with rebuild scripts when page meta missing
            page_char_counts: list[tuple[int, int]] = []
            for i, p in enumerate(pages, start=1):
                meta = p.metadata.get("page")
                page_no = int(meta) + 1 if isinstance(meta, int) else i
                n_chars = len(p.page_content or "")
                page_char_counts.append((page_no, n_chars))
                # Count chunks whose metadata page matches
                n_chunks_page = sum(
                    1
                    for c in chunks
                    if (
                        int(c.metadata.get("page")) + 1
                        if isinstance(c.metadata.get("page"), int)
                        else None
                    )
                    == page_no
                )
                chars_per_page.append((page_no, n_chars, n_chunks_page))

            low_text = [(pn, ch) for pn, ch in page_char_counts if ch < 100]
            # Long pages that produced only one chunk (chunking failed to split)
            long_unsplit = [
                (pn, ch)
                for pn, ch, nc in chars_per_page
                if ch > chunk_size and nc <= 1
            ]
            # Repeated header/footer heuristic: first line of many pages identical
            first_lines = [
                (p.page_content or "").strip().splitlines()[0][:80]
                for p in pages
                if (p.page_content or "").strip()
            ]
            line_counts = Counter(first_lines)
            repeated = [
                f"{n}× {line!r}"
                for line, n in line_counts.most_common(3)
                if n >= 5 and len(line) > 8
            ]

            multi_chunk_pages = sum(1 for _, _, nc in chars_per_page if nc > 1)
            reports.append(
                {
                    "file": pdf.name,
                    "pages_extracted": len(pages),
                    "chunks": len(chunks),
                    "chars_total": sum(ch for _, ch in page_char_counts),
                    "chars_per_page_sample": chars_per_page[:5],
                    "chars_min": min((ch for _, ch in page_char_counts), default=0),
                    "chars_max": max((ch for _, ch in page_char_counts), default=0),
                    "low_text_pages": low_text[:20],
                    "long_unsplit": long_unsplit[:20],
                    "repeated_header_examples": repeated,
                    "multi_chunk_pages": multi_chunk_pages,
                    "chunking_splits_long_pages": len(long_unsplit) == 0,
                }
            )
    finally:
        settings.chunk_size = old_size
        settings.chunk_overlap = old_overlap
    return reports


def diagnose(
    *,
    questions_path: Path | str | None = None,
    config_name: str = "default",
) -> dict[str, Any]:
    config = load_config(config_name)
    qpath = Path(questions_path or Path(__file__).parent / "data" / "questions.jsonl")
    questions = load_questions(qpath)
    index = build_or_load_eval_index(config, subset="primary")
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
    ingest = ingest_audit_real(config)

    mean_ov = sum(o for _, o in overlaps) / len(overlaps) if overlaps else None
    cat_means = {c: (sum(v) / len(v) if v else None) for c, v in sorted(by_cat.items())}

    return {
        "corpus_subset": "primary",
        "corpus_dir": str(REAL_DIR),
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
        "recall_at_4_ablation": ablation["overall"],
        "recall_at_4_by_category": ablation["by_category"],
        "recall_at_4_by_category_n": ablation["by_category_n"],
        "hybrid_vs_faiss_gap": ablation["hybrid_vs_faiss_gap"],
        "bm25_miss_examples": ablation["bm25_miss_examples"],
        "ingest_audit": ingest,
    }


def render_difficulty_md(diag: dict[str, Any], *, title: str = "Eval difficulty") -> str:
    ab = diag.get("recall_at_4_ablation") or {}
    lines = [
        f"# {title}",
        "",
        "Generated by `python -m evals.difficulty`. Numbers are from a real run on the",
        "isolated **primary** (`evals/corpus/real/`) eval index — not portfolio headline",
        "claims (labels may be draft). Synthetic fixtures are excluded from this index.",
        "",
        "## Corpus / index",
        "",
        f"- Subset: **{diag.get('corpus_subset', 'primary')}** (`{diag.get('corpus_dir', '')}`)",
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
    ]
    if diag["mean_query_span_overlap"] is not None:
        lines.append(
            f"- Mean overlap: **{diag['mean_query_span_overlap']:.4f}**"
        )
    else:
        lines.append("- Mean overlap: —")
    lines += [
        f"- Answerable questions scored: {diag['n_answerable_overlap']} / {diag['n_questions']}",
        "",
        "| Category | Mean overlap |",
        "|----------|--------------|",
    ]
    for cat, val in (diag.get("overlap_by_category") or {}).items():
        lines.append(f"| {cat} | {val:.4f} |" if val is not None else f"| {cat} | — |")

    lines += [
        "",
        "## Recall@4 by retriever (answerable, draft labels OK)",
        "",
        "| Mode | Recall@4 |",
        "|------|----------|",
        f"| hybrid_rrf | {_fmt(ab.get('hybrid'))} |",
        f"| faiss_only | {_fmt(ab.get('faiss_only'))} |",
        f"| bm25_only | {_fmt(ab.get('bm25_only'))} |",
        f"",
        f"- Hybrid − FAISS-only gap: **{_fmt(diag.get('hybrid_vs_faiss_gap'))}** "
        f"(recorded without fixing)",
        "",
        "## Recall@4 by category (hybrid / faiss_only / bm25_only)",
        "",
        "| Category | n | hybrid | faiss_only | bm25_only |",
        "|----------|---|--------|------------|-----------|",
    ]
    by_cat = diag.get("recall_at_4_by_category") or {}
    by_n = diag.get("recall_at_4_by_category_n") or {}
    for cat, modes in by_cat.items():
        lines.append(
            f"| {cat} | {by_n.get(cat, 0)} | {_fmt(modes.get('hybrid'))} | "
            f"{_fmt(modes.get('faiss_only'))} | {_fmt(modes.get('bm25_only'))} |"
        )

    lines += [
        "",
        "## BM25 miss examples (gold not in BM25 top-4)",
        "",
        "Recorded without fixing. Tokens use the same `_tokenize` as BM25 "
        "(whitespace `split().lower()`).",
        "",
    ]
    misses = diag.get("bm25_miss_examples") or []
    if not misses:
        lines.append("_No BM25 misses among answerable questions in this run._")
    for i, m in enumerate(misses, 1):
        lines += [
            f"### {i}. `{m['id']}` ({m.get('category')})",
            "",
            f"- Query: {m['query']}",
            f"- Query tokens: `{' '.join(m.get('query_tokens') or [])}`",
            f"- Gold files: {', '.join(m.get('gold_filenames') or [])}",
            f"- Gold chunk tokens (sample): "
            f"`{' '.join((m.get('gold_chunk_tokens_sample') or [])[:40])}`",
            "",
        ]

    lines += [
        "## Ingestion audit (primary / real) — Phase 3 backlog",
        "",
        "Do **not** change ingestion yet. Issues below are for Phase 3.",
        "",
    ]
    for rep in diag.get("ingest_audit") or []:
        lines += [
            f"### `{rep['file']}`",
            "",
            f"- Pages extracted: **{rep['pages_extracted']}**; chunks: **{rep['chunks']}**; "
            f"chars total: **{rep['chars_total']}**",
            f"- Chars/page min–max: **{rep['chars_min']}–{rep['chars_max']}**",
            f"- Multi-chunk pages: **{rep['multi_chunk_pages']}**; "
            f"chunking splits all long pages: **{rep['chunking_splits_long_pages']}**",
        ]
        if rep.get("low_text_pages"):
            sample = ", ".join(f"p{p}({c}c)" for p, c in rep["low_text_pages"][:8])
            lines.append(f"- Low-text pages (<100 chars): {sample}")
        if rep.get("long_unsplit"):
            sample = ", ".join(f"p{p}({c}c)" for p, c in rep["long_unsplit"][:8])
            lines.append(
                f"- Long pages (>{1000} chars) still single-chunk: {sample}"
            )
        if rep.get("repeated_header_examples"):
            lines.append(
                "- Repeated headers/footers: "
                + "; ".join(rep["repeated_header_examples"])
            )
        sample_rows = rep.get("chars_per_page_sample") or []
        if sample_rows:
            lines.append(
                "- Sample (page, chars, chunks): "
                + ", ".join(f"({a},{b},{c})" for a, b, c in sample_rows)
            )
        lines.append("")

    lines += [
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
    diag = diagnose()
    out = Path(__file__).parent / "DIFFICULTY.md"
    out.write_text(render_difficulty_md(diag), encoding="utf-8")
    audit_path = Path(__file__).parent / "results" / "_ingest_audit_real.json"
    audit_path.parent.mkdir(parents=True, exist_ok=True)
    audit_path.write_text(
        json.dumps(diag.get("ingest_audit") or [], indent=2), encoding="utf-8"
    )
    printable = {
        k: diag[k]
        for k in diag
        if k not in {"per_question_overlap", "ingest_audit", "bm25_miss_examples"}
    }
    printable["bm25_miss_ids"] = [m["id"] for m in (diag.get("bm25_miss_examples") or [])]
    printable["ingest_files"] = [
        r["file"] for r in (diag.get("ingest_audit") or [])
    ]
    print(json.dumps(printable, indent=2))
    print(f"wrote {out}")
    print(f"wrote {audit_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
