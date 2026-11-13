"""Evaluation runner against the isolated eval index (never the live app index)."""

from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.corpus_util import corpus_hash
from evals.eval_index import build_or_load_eval_index, search_eval_index
from evals.metrics import (
    false_refusal_rate,
    hit_rate,
    latency_summary,
    mrr,
    not_found_accuracy,
    precision_at_k,
    recall_at_1,
    recall_at_4,
    recall_at_k,
    refusal_precision,
    refusal_recall,
)
from evals.schema import filter_questions, load_questions
from evals.span_map import GoldSpan, ranks_of_relevant

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_QUESTIONS = Path(__file__).resolve().parent / "data" / "questions.jsonl"
RESULTS_DIR = Path(__file__).resolve().parent / "results"


def git_commit_hash() -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=str(ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return out.strip()
    except Exception:
        return "unknown"


def load_config(name_or_path: str) -> dict[str, Any]:
    path = Path(name_or_path)
    if not path.is_file():
        path = Path(__file__).resolve().parent / "configs" / f"{name_or_path}.json"
    if not path.is_file():
        return {
            "name": name_or_path,
            "retriever_top_k": 4,
            "span_min_overlap": 0.5,
            "llm_provider": "extractive",
            "chunk_size": 1000,
            "chunk_overlap": 200,
            "embedding_provider": "local",
            "hybrid_search_weight": 0.5,
        }
    data = json.loads(path.read_text(encoding="utf-8"))
    data.setdefault("name", path.stem)
    return data


def evaluate(
    *,
    config_name: str = "default",
    split: str = "test",
    verified_only: bool = False,
    questions_path: Path | str = DEFAULT_QUESTIONS,
    out_dir: Path | str = RESULTS_DIR,
) -> dict[str, Any]:
    config = load_config(config_name)
    questions = filter_questions(
        load_questions(questions_path),
        split=split,
        verified_only=verified_only,
    )
    n_verified = sum(1 for q in questions if q.label_source == "human_verified")
    n_draft = sum(1 for q in questions if q.label_source == "draft")
    c_hash = corpus_hash(subset="primary")

    # Build/load isolated index BEFORE any retrieval (never touches app FAISS)
    eval_index = build_or_load_eval_index(config)

    meta: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "git_commit": git_commit_hash(),
        "config": config,
        "corpus_hash": c_hash,
        "chunking_config_hash": eval_index.chunking_config_hash,
        "eval_index_path": str(eval_index.path),
        "split": split,
        "verified_only": verified_only,
        "n_questions": len(questions),
        "n_human_verified": n_verified,
        "n_draft": n_draft,
        "questions_path": str(questions_path),
        "indexed_chunks": eval_index.n_chunks,
        "uses_app_index": False,
    }

    if not questions:
        report = {
            **meta,
            "skipped": True,
            "reason": "no questions matched filters — add evals/data/questions.jsonl",
            "metrics": {},
            "cases": [],
        }
        return _write(report, out_dir, config.get("name", config_name), split)

    if eval_index.n_chunks == 0:
        report = {
            **meta,
            "skipped": True,
            "reason": "empty eval corpus index — add PDFs under evals/corpus/",
            "metrics": {},
            "cases": [],
        }
        return _write(report, out_dir, config.get("name", config_name), split)

    top_k = int(config.get("retriever_top_k", 4))
    min_overlap = float(config.get("span_min_overlap", 0.5))
    dense_w = float(config.get("hybrid_search_weight", 0.5))

    cases: list[dict[str, Any]] = []
    recall1: list[float] = []
    recall4: list[float] = []
    recall_k_vals: list[float] = []
    prec4: list[float] = []
    mrrs: list[float] = []
    hits: list[bool] = []
    pred_refuse: list[bool] = []
    gold_unans: list[bool] = []
    latencies: list[float] = []

    for q in questions:
        t0 = time.perf_counter()
        detailed = search_eval_index(
            eval_index,
            q.query,
            top_k=top_k,
            dense_weight=dense_w,
        )
        ms = (time.perf_counter() - t0) * 1000
        latencies.append(ms)

        ranks = ranks_of_relevant(
            [GoldSpan(g.filename, g.page, g.span) for g in q.gold],
            detailed.results,
            min_overlap=min_overlap,
        )
        refused = len(detailed.results) == 0
        pred_refuse.append(refused)
        gold_unans.append(not q.answerable)

        r1 = recall_at_1(ranks)
        r4 = recall_at_4(ranks)
        rk = recall_at_k(ranks, top_k)
        p4 = precision_at_k(ranks, min(4, top_k))
        mr = mrr(ranks)
        hit = bool(ranks)

        if q.answerable:
            recall1.append(r1)
            recall4.append(r4)
            recall_k_vals.append(rk)
            prec4.append(p4)
            mrrs.append(mr)
            hits.append(hit)

        cases.append(
            {
                "id": q.id,
                "category": q.category,
                "answerable": q.answerable,
                "label_source": q.label_source,
                "relevant_ranks": ranks,
                "recall_at_1": r1 if q.answerable else None,
                "recall_at_4": r4 if q.answerable else None,
                "mrr": mr if q.answerable else None,
                "n_results": len(detailed.results),
                "refused_empty_retrieval": refused,
                "latency_ms": round(ms, 2),
                "faiss_ms": detailed.details.get("faiss_ms"),
                "bm25_ms": detailed.details.get("bm25_ms"),
            }
        )

    def _avg(xs: list[float]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    metrics = {
        "Recall@1": _avg(recall1),
        "Recall@4": _avg(recall4),
        f"Recall@{top_k}": _avg(recall_k_vals),
        "Precision@4": _avg(prec4),
        "MRR": _avg(mrrs),
        "hit_rate": hit_rate(hits) if hits else None,
        "not_found_accuracy": not_found_accuracy(pred_refuse, gold_unans),
        "refusal_precision": refusal_precision(pred_refuse, gold_unans),
        "refusal_recall": refusal_recall(pred_refuse, gold_unans),
        "false_refusal_rate": false_refusal_rate(pred_refuse, gold_unans),
        "key_fact_coverage": None,
        "latency": latency_summary(latencies),
        "notes": {
            "retrieval_only": (
                "Scores retrieval on the isolated eval index built from evals/corpus/. "
                "Does not use the app FAISS/BM25 or SQLite."
            ),
            "label_integrity": (
                "Draft labels are unverified. Headline claims require "
                "label_source=human_verified and verified_only=true."
            ),
        },
    }

    report = {
        **meta,
        "skipped": False,
        "metrics": metrics,
        "cases": cases,
    }
    return _write(report, out_dir, config.get("name", config_name), split)


def _write(report: dict[str, Any], out_dir: Path | str, config_name: str, split: str) -> dict[str, Any]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    date = datetime.now(timezone.utc).strftime("%Y%m%d")
    json_path = out / f"{date}_{config_name}_{split}.json"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path = out / f"{date}_{config_name}_{split}.md"
    md_path.write_text(_markdown_summary(report, json_path), encoding="utf-8")
    report["results_json"] = str(json_path)
    report["results_md"] = str(md_path)
    return report


def _markdown_summary(report: dict[str, Any], json_path: Path) -> str:
    m = report.get("metrics") or {}
    lines = [
        f"# Eval report — {report.get('config', {}).get('name', 'config')}",
        "",
        f"- Generated: `{report.get('generated_at')}`",
        f"- Git commit: `{report.get('git_commit')}`",
        f"- Corpus hash: `{report.get('corpus_hash')}`",
        f"- Chunking config hash: `{report.get('chunking_config_hash')}`",
        f"- Eval index: `{report.get('eval_index_path')}`",
        f"- Uses app index: `{report.get('uses_app_index')}`",
        f"- Split: `{report.get('split')}`",
        f"- Questions: {report.get('n_questions')} "
        f"(human_verified={report.get('n_human_verified')}, draft={report.get('n_draft')})",
        f"- Verified-only filter: `{report.get('verified_only')}`",
        f"- Results JSON: `{json_path.as_posix()}`",
        "",
    ]
    if report.get("skipped"):
        lines += [f"**Skipped:** {report.get('reason')}", ""]
        return "\n".join(lines)

    lines += ["## Metrics", "", "| Metric | Value |", "|--------|-------|"]
    for key in (
        "Recall@1",
        "Recall@4",
        "MRR",
        "Precision@4",
        "hit_rate",
        "not_found_accuracy",
        "refusal_precision",
        "refusal_recall",
        "false_refusal_rate",
    ):
        val = m.get(key)
        display = "—" if val is None else f"{val:.4f}"
        lines.append(f"| {key} | {display} |")
    lat = m.get("latency") or {}
    lines += [
        "",
        f"Latency p50: {lat.get('p50_ms')} ms · p95: {lat.get('p95_ms')} ms",
        "",
        "### Notes",
        "",
        str((m.get("notes") or {}).get("retrieval_only") or ""),
        "",
        str((m.get("notes") or {}).get("label_integrity") or ""),
        "",
    ]
    return "\n".join(lines)
