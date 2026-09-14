"""
Offline RAG evaluation harness for DocuMind AI.

Runs retrieval + (optional) answer checks against evals/dataset.json.
Does not invent scores — prints measured metrics only.

Usage (from repo root, venv active, backend not required for unit checks):

  python -m evals.run_eval              # structural + local retrieval if index exists
  python -m evals.run_eval --api        # hit live API at localhost:8000
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATASET = Path(__file__).resolve().parent / "dataset.json"


def _load_cases() -> list[dict]:
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    return list(data.get("cases") or [])


def eval_retrieval_local() -> dict:
    """Evaluate hybrid retrieval against an existing FAISS index (if present)."""
    from backend.app.rag.hybrid_search import hybrid_search_detailed
    from backend.app.rag.qa_chain import NOT_FOUND_MESSAGE, expand_followup_query
    from backend.app.rag.vector_store import get_vector_store

    store = get_vector_store()
    n_docs = len(getattr(store.docstore, "_dict", {}) or {})
    if n_docs == 0:
        return {"skipped": True, "reason": "empty vector store — upload a PDF first"}

    cases = _load_cases()
    rows = []
    for case in cases:
        q = case["question"]
        detailed = hybrid_search_detailed(q)
        joined = " ".join(d.page_content for d, _ in detailed.results).lower()
        keywords = [k.lower() for k in case.get("relevant_keywords") or []]
        hit = True
        if keywords:
            hit = any(k in joined for k in keywords)
        if case.get("expect_not_found"):
            # For unanswerable questions we only check that retrieval still returns
            # somehow; groundedness is validated via answer path when --api is used.
            hit = True
        rows.append(
            {
                "id": case["id"],
                "keyword_hit": hit,
                "n_results": len(detailed.results),
                "latency_ms": detailed.details.get("latency_ms"),
            }
        )

    # Follow-up expansion sanity
    expanded = expand_followup_query(
        "Which of them are used in projects?",
        ["What technologies are mentioned?"],
    )
    followup_ok = "technologies" in expanded.lower()

    measured = {
        "skipped": False,
        "indexed_chunks": n_docs,
        "cases": rows,
        "keyword_hit_rate": (
            sum(1 for r in rows if r["keyword_hit"]) / len(rows) if rows else 0.0
        ),
        "followup_expansion_ok": followup_ok,
        "not_found_message": NOT_FOUND_MESSAGE,
    }
    return measured


def eval_via_api(base: str = "http://127.0.0.1:8000/api/v1") -> dict:
    import httpx

    cases = _load_cases()
    rows = []
    with httpx.Client(timeout=120.0) as client:
        health = client.get(f"{base}/health")
        health.raise_for_status()
        for case in cases:
            r = client.post(
                f"{base}/chat",
                json={"message": case["question"], "stream": False},
            )
            r.raise_for_status()
            data = r.json()
            answer = (data.get("answer") or "").lower()
            expected = [e.lower() for e in case.get("expected_answer_contains") or []]
            contains_ok = all(e in answer for e in expected) if expected else True
            if case.get("expect_not_found"):
                contains_ok = "couldn't find" in answer
            rows.append(
                {
                    "id": case["id"],
                    "grounded_check": contains_ok,
                    "confidence": data.get("confidence"),
                    "n_sources": len(data.get("sources") or []),
                    "cached": data.get("cached"),
                    "retrieval_ms": (data.get("timings") or {}).get("retrieval_ms"),
                }
            )
    return {
        "cases": rows,
        "pass_rate": sum(1 for r in rows if r["grounded_check"]) / len(rows) if rows else 0.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DocuMind RAG evaluation")
    parser.add_argument("--api", action="store_true", help="Evaluate via live chat API")
    parser.add_argument("--base", default="http://127.0.0.1:8000/api/v1")
    args = parser.parse_args()

    print("=== DocuMind eval ===")
    local = eval_retrieval_local()
    print(json.dumps({"local_retrieval": local}, indent=2))
    if args.api:
        api = eval_via_api(args.base)
        print(json.dumps({"api_chat": api}, indent=2))
    else:
        print("Tip: re-run with --api after starting the backend for answer groundedness checks.")


if __name__ == "__main__":
    main()
