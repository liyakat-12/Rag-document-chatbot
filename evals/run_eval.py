"""
Offline RAG evaluation harness for DocuMind AI.

Runs retrieval (+ optional live API answer checks) against evals/dataset.json.
Does not invent scores — prints and optionally exports measured metrics only.

Usage (from repo root, venv active):

  python -m evals.run_eval
  python -m evals.run_eval --api --base http://127.0.0.1:8001/api/v1
  python -m evals.run_eval --out evals/last_report.json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import time
from datetime import datetime, timezone
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
    from backend.app.rag.qa_chain import (
        NOT_FOUND_MESSAGE,
        expand_followup_query,
        retrieve_detailed,
    )
    from backend.app.rag.vector_store import get_vector_store

    store = get_vector_store()
    n_docs = len(getattr(store.docstore, "_dict", {}) or {})
    if n_docs == 0:
        return {"skipped": True, "reason": "empty vector store — upload a PDF first"}

    cases = _load_cases()
    rows = []
    latencies: list[float] = []
    for case in cases:
        q = case["question"]
        t0 = time.perf_counter()
        detailed = asyncio.run(retrieve_detailed(q))
        ms = (time.perf_counter() - t0) * 1000
        latencies.append(ms)
        joined = " ".join(d.page_content for d, _ in detailed.results).lower()
        keywords = [k.lower() for k in case.get("relevant_keywords") or []]
        hit = True
        if keywords:
            hit = any(k in joined for k in keywords)
        if case.get("expect_not_found"):
            hit = True
        rows.append(
            {
                "id": case["id"],
                "keyword_hit": hit,
                "n_results": len(detailed.results),
                "latency_ms": round(ms, 2),
                "faiss_ms": (detailed.details.get("semantic") or {}).get("latency_ms"),
                "bm25_ms": (detailed.details.get("bm25") or {}).get("latency_ms"),
                "parallel": detailed.details.get("parallel"),
                "retrieval_strategy": detailed.details.get("strategy"),
                "query_variants": detailed.details.get("query_variants", [q]),
                "reranker": (
                    (detailed.details.get("reranker") or {}).get("model")
                    or (detailed.details.get("reranker") or {}).get("fallback")
                    or (
                        "enabled"
                        if (detailed.details.get("reranker") or {}).get("enabled")
                        else "disabled"
                    )
                ),
            }
        )

    expanded = expand_followup_query(
        "Which of them are used in projects?",
        ["What technologies are mentioned?"],
    )
    followup_ok = "technologies" in expanded.lower()
    lat_sorted = sorted(latencies)

    return {
        "skipped": False,
        "indexed_chunks": n_docs,
        "n_cases": len(rows),
        "cases": rows,
        "keyword_hit_rate": (
            sum(1 for r in rows if r["keyword_hit"]) / len(rows) if rows else 0.0
        ),
        "followup_expansion_ok": followup_ok,
        "retrieval_mode": (
            rows[0].get("retrieval_strategy") if rows else "unknown"
        ),
        "not_found_message": NOT_FOUND_MESSAGE,
        "latency_ms": {
            "avg": round(sum(latencies) / len(latencies), 2) if latencies else None,
            "p50": round(lat_sorted[len(lat_sorted) // 2], 2) if lat_sorted else None,
            "p95": (
                round(lat_sorted[min(len(lat_sorted) - 1, int(len(lat_sorted) * 0.95))], 2)
                if lat_sorted
                else None
            ),
        },
        "metric_notes": {
            "keyword_hit_rate": (
                "Proxy for retrieval relevance using case.relevant_keywords against "
                "concatenated top-k chunk text. Not gold-chunk Recall@K unless the "
                "dataset includes chunk IDs."
            ),
            "Recall@K": "unavailable — dataset does not ship gold chunk IDs",
            "MRR": "unavailable — dataset does not ship gold chunk IDs",
        },
    }


def eval_via_api(base: str = "http://127.0.0.1:8001/api/v1") -> dict:
    import httpx

    cases = _load_cases()
    rows = []
    with httpx.Client(timeout=120.0) as client:
        health = client.get(f"{base}/health")
        health.raise_for_status()
        app = health.json()
        for case in cases:
            t0 = time.perf_counter()
            r = client.post(
                f"{base}/chat",
                json={"message": case["question"], "stream": False},
            )
            r.raise_for_status()
            data = r.json()
            total_ms = (time.perf_counter() - t0) * 1000
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
                    "generation_ms": (data.get("timings") or {}).get("generation_ms"),
                    "total_ms": round(total_ms, 2),
                }
            )
    return {
        "base": base,
        "health": {
            "app": app.get("app"),
            "llm_provider": app.get("llm_provider"),
            "embedding_provider": app.get("embedding_provider"),
        },
        "cases": rows,
        "pass_rate": sum(1 for r in rows if r["grounded_check"]) / len(rows) if rows else 0.0,
        "n_cases": len(rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="DocuMind RAG evaluation")
    parser.add_argument("--api", action="store_true", help="Evaluate via live chat API")
    parser.add_argument(
        "--base",
        default="http://127.0.0.1:8001/api/v1",
        help="API base (default 8001 — DocuMind often shares the machine with other apps on 8000)",
    )
    parser.add_argument("--out", default="", help="Write JSON report to this path")
    args = parser.parse_args()

    report: dict = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "dataset": str(DATASET),
    }
    print("=== DocuMind eval ===")
    local = eval_retrieval_local()
    report["local_retrieval"] = local
    print(json.dumps({"local_retrieval": local}, indent=2))
    if args.api:
        api = eval_via_api(args.base)
        report["api_chat"] = api
        print(json.dumps({"api_chat": api}, indent=2))
    else:
        print("Tip: re-run with --api --base http://127.0.0.1:8001/api/v1 for answer checks.")

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote report → {out}")


if __name__ == "__main__":
    main()
