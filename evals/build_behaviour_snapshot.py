"""Build default-behaviour snapshot for regression (primary eval index + extractive).

Usage:
  python -m evals.build_behaviour_snapshot

Writes evals/results/_default_behaviour_snapshot.json
Does not modify questions.jsonl.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force extractive offline defaults for snapshot reproducibility
os.environ["LLM_PROVIDER"] = "extractive"
os.environ.setdefault("EMBEDDING_PROVIDER", "local")
os.environ.setdefault("SEMANTIC_CACHE_ENABLED", "false")

OUT = Path(__file__).resolve().parent / "results" / "_default_behaviour_snapshot.json"
QUESTIONS = Path(__file__).resolve().parent / "data" / "questions.jsonl"


async def _one(index, q, config) -> dict:
    from evals.eval_index import search_eval_index
    from backend.app.rag.qa_chain import build_qa_result, generate_answer

    detailed = search_eval_index(
        index,
        q.query,
        top_k=10,
        dense_weight=float(config.get("hybrid_search_weight", 0.5)),
    )
    docs = detailed.results
    answer, _tokens = await generate_answer(q.query, docs)
    packaged = build_qa_result(answer, docs, retrieval=detailed.details)
    chunk_ids = [
        str(doc.metadata.get("chunk_id") or "")
        for doc, _ in docs
    ]
    citations = [
        {
            "chunk_id": c.get("chunk_id"),
            "filename": c.get("filename"),
            "page_number": c.get("page_number"),
            "document_id": c.get("document_id"),
        }
        for c in packaged["sources"]
    ]
    return {
        "id": q.id,
        "query": q.query,
        "top10_chunk_ids": chunk_ids,
        "answer": packaged["answer"],
        "citations": citations,
    }


async def build() -> dict:
    from backend.app.config import get_settings

    get_settings.cache_clear()

    from evals.eval_index import build_or_load_eval_index
    from evals.runner import load_config
    from evals.schema import load_questions

    config = load_config("default")
    questions = load_questions(QUESTIONS)
    index = build_or_load_eval_index(config, subset="primary")

    cases = []
    for q in questions:
        cases.append(await _one(index, q, config))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus_subset": "primary",
        "corpus_hash": index.corpus_hash,
        "chunking_config_hash": index.chunking_config_hash,
        "n_questions": len(cases),
        "retriever_top_k_snapshot": 10,
        "llm_provider": "extractive",
        "cases": cases,
    }


def main() -> int:
    data = asyncio.run(build())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"wrote {OUT} ({data['n_questions']} questions)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
