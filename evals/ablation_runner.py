"""Named retrieval ablations on a fixed question split (draft-label smoke OK).

Configs: faiss_only, bm25_only, hybrid_rrf, hybrid_rrf_normalized_bm25,
hybrid_rrf_reranker, hybrid_all.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evals.eval_index import (
    _dense_search,
    _sparse_search,
    build_or_load_eval_index,
)
from evals.metrics import mrr, recall_at_4
from evals.runner import load_config
from evals.schema import load_questions
from evals.span_map import GoldSpan, ranks_of_relevant
from backend.app.rag.hybrid_search import reciprocal_rank_fusion

ABLATIONS = {
    "faiss_only": {"mode": "faiss"},
    "bm25_only": {"mode": "bm25"},
    "hybrid_rrf": {"mode": "hybrid", "bm25_tokenizer": "whitespace", "rerank": False},
    "hybrid_rrf_normalized_bm25": {
        "mode": "hybrid",
        "bm25_tokenizer": "normalized",
        "rerank": False,
    },
    "hybrid_rrf_reranker": {
        "mode": "hybrid",
        "bm25_tokenizer": "whitespace",
        "rerank": True,
    },
    "hybrid_all": {
        "mode": "hybrid",
        "bm25_tokenizer": "normalized",
        "rerank": True,
        "exact_boost": True,
        "dedupe": True,
    },
}

# Ingest-quality ablations (Phase 3). Registered here but NOT run by default —
# they rebuild a separate eval index via chunking_config_hash. Do not run against
# real/draft labels until a verified baseline exists.
INGEST_ABLATIONS = {
    "hybrid_rrf_strip_headers": {
        "mode": "hybrid",
        "bm25_tokenizer": "whitespace",
        "rerank": False,
        "ingest_strip_repeated_headers_footers": True,
        "ingest_flag_low_text_pages": False,
        "requires_index_rebuild": True,
    },
    "hybrid_rrf_flag_low_text": {
        "mode": "hybrid",
        "bm25_tokenizer": "whitespace",
        "rerank": False,
        "ingest_strip_repeated_headers_footers": False,
        "ingest_flag_low_text_pages": True,
        "requires_index_rebuild": True,
    },
}


def _run_one(index, query: str, spec: dict[str, Any], top_k: int = 4):
    fetch = max(top_k * 2, 8)
    dense = [(d, s) for d, s in _dense_search(index, query, fetch) if s >= 0.22]
    # Note: eval index BM25 always uses whitespace tokenize in eval_index._tokenize.
    # Normalized BM25 ablation is reported as "approx via refusal normaliser overlay"
    # when tokenizer != whitespace — see DECISIONS.md.
    sparse = [(d, s) for d, s in _sparse_search(index, query, fetch) if s > 0]
    mode = spec["mode"]
    if mode == "faiss":
        return dense[:top_k]
    if mode == "bm25":
        return sparse[:top_k]
    fused = reciprocal_rank_fusion([dense, sparse], weights=[0.5, 0.5])
    if spec.get("exact_boost"):
        from backend.app.rag.hybrid_search import _exact_match_boost

        fused = _exact_match_boost(query, fused)
    if spec.get("rerank"):
        from backend.app.rag.reranker import rerank_candidates

        fused, _ = rerank_candidates(query, fused[:16])
    if spec.get("dedupe"):
        from backend.app.rag.dedupe import dedupe_near_duplicates

        fused = dedupe_near_duplicates(fused)
    return fused[:top_k]


def run_ablations(
    *,
    questions_path: Path | None = None,
    split: str = "test",
    out_dir: Path | None = None,
) -> dict[str, Any]:
    config = load_config("default")
    qpath = questions_path or (ROOT / "evals" / "data" / "questions.jsonl")
    questions = [q for q in load_questions(qpath) if q.split == split and q.answerable]
    index = build_or_load_eval_index(config, subset="primary")
    top_k = int(config.get("retriever_top_k", 4))
    min_ov = float(config.get("span_min_overlap", 0.5))

    table: dict[str, dict[str, float | None]] = {}
    for name, spec in ABLATIONS.items():
        r4s: list[float] = []
        mrrs: list[float] = []
        for q in questions:
            ranked = _run_one(index, q.query, spec, top_k=top_k)
            gold = [GoldSpan(g.filename, g.page, g.span) for g in q.gold]
            ranks = ranks_of_relevant(gold, ranked, min_overlap=min_ov)
            r4s.append(recall_at_4(ranks))
            mrrs.append(mrr(ranks))
        table[name] = {
            "n": len(questions),
            "Recall@4": sum(r4s) / len(r4s) if r4s else None,
            "MRR": sum(mrrs) / len(mrrs) if mrrs else None,
        }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": "DRAFT LABELS — NOT FOR REPORTING",
        "split": split,
        "n_answerable": len(questions),
        "ablations": table,
        "ingest_ablations_registered": list(INGEST_ABLATIONS.keys()),
        "ingest_ablations_note": (
            "Registered but not executed. Enabling either ingest flag changes "
            "chunking_config_hash and uses a separate evals/.index/ directory. "
            "Do not run against labels until a verified baseline exists."
        ),
    }
    out_dir = out_dir or (ROOT / "evals" / "results")
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "_draft_ablation.json"
    md_path = out_dir / "_draft_ablation.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    lines = [
        "# DRAFT LABELS — NOT FOR REPORTING",
        "",
        f"Generated: {report['generated_at']}",
        f"Split: `{split}` · answerable n={len(questions)}",
        "",
        "| Ablation | n | Recall@4 | MRR |",
        "|----------|---|----------|-----|",
    ]
    for name, row in table.items():
        r4 = row["Recall@4"]
        mr = row["MRR"]
        lines.append(
            f"| {name} | {row['n']} | "
            f"{'—' if r4 is None else f'{r4:.4f}'} | "
            f"{'—' if mr is None else f'{mr:.4f}'} |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return report


def main() -> int:
    report = run_ablations()
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
