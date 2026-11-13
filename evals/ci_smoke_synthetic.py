"""CI smoke eval on the synthetic corpus + questions_synthetic.jsonl."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

THRESHOLDS = ROOT / "evals" / "configs" / "ci_thresholds.json"
QUESTIONS = ROOT / "evals" / "data" / "questions_synthetic.jsonl"
OUT_JSON = ROOT / "evals" / "results" / "_ci_synthetic_smoke.json"
OUT_MD = ROOT / "evals" / "results" / "_ci_synthetic_smoke.md"


def main() -> int:
    from evals.eval_index import build_or_load_eval_index, search_eval_index
    from evals.metrics import not_found_accuracy, recall_at_4
    from evals.runner import load_config
    from evals.schema import load_questions
    from evals.span_map import GoldSpan, ranks_of_relevant

    thr = json.loads(THRESHOLDS.read_text(encoding="utf-8"))
    config = load_config("default")
    questions = [q for q in load_questions(QUESTIONS) if q.split == thr.get("split", "test")]
    index = build_or_load_eval_index(config, subset="synthetic")
    top_k = int(config.get("retriever_top_k", 4))
    min_ov = float(config.get("span_min_overlap", 0.5))

    r4s: list[float] = []
    pred_refuse: list[bool] = []
    gold_unans: list[bool] = []
    for q in questions:
        detailed = search_eval_index(index, q.query, top_k=top_k)
        ranks = ranks_of_relevant(
            [GoldSpan(g.filename, g.page, g.span) for g in q.gold],
            detailed.results,
            min_overlap=min_ov,
        )
        if q.answerable:
            r4s.append(recall_at_4(ranks))
        refused = len(detailed.results) == 0
        pred_refuse.append(refused)
        gold_unans.append(not q.answerable)

    recall = sum(r4s) / len(r4s) if r4s else 0.0
    nfa = not_found_accuracy(pred_refuse, gold_unans) or 0.0
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": "DRAFT LABELS — CI SMOKE ONLY",
        "corpus_subset": "synthetic",
        "n_questions": len(questions),
        "n_answerable": len(r4s),
        "Recall@4": recall,
        "not_found_accuracy": nfa,
        "thresholds": thr,
        "pass": recall >= float(thr["min_recall_at_4"])
        and nfa >= float(thr["min_not_found_accuracy"]),
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")
    OUT_MD.write_text(
        "# DRAFT LABELS — CI SMOKE ONLY\n\n"
        f"- Recall@4: **{recall:.4f}** (min {thr['min_recall_at_4']})\n"
        f"- not_found_accuracy: **{nfa:.4f}** (min {thr['min_not_found_accuracy']})\n"
        f"- pass: **{report['pass']}**\n",
        encoding="utf-8",
    )
    print(json.dumps(report, indent=2))
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
