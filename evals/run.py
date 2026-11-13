"""CLI: python -m evals.run --config default --split test

Writes evals/results/<date>_<config>_<split>.json and .md
Does not overwrite baseline.json (Phase 2). Does not invent metrics.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="DocuMind evaluation runner (span-gold)")
    parser.add_argument("--config", default="default", help="Config name or path under evals/configs/")
    parser.add_argument("--split", choices=["tune", "test", "all"], default="test")
    parser.add_argument(
        "--verified-only",
        action="store_true",
        help="Score only label_source=human_verified questions",
    )
    parser.add_argument(
        "--questions",
        default=str(Path(__file__).resolve().parent / "data" / "questions.jsonl"),
    )
    parser.add_argument(
        "--out-dir",
        default=str(Path(__file__).resolve().parent / "results"),
    )
    parser.add_argument(
        "--followups",
        action="store_true",
        help="Evaluate draft two-turn follow-ups (evals/data/questions_followups.jsonl)",
    )
    args = parser.parse_args(argv)

    if args.followups:
        from evals.followups import evaluate_followups

        report = evaluate_followups(split=None if args.split == "all" else args.split)
        print(json.dumps({k: report.get(k) for k in report if k != "cases"}, indent=2))
        return 0

    from evals.runner import evaluate

    split = args.split
    if split == "all":
        # Run both splits separately for clarity
        codes = 0
        for s in ("tune", "test"):
            report = evaluate(
                config_name=args.config,
                split=s,
                verified_only=args.verified_only,
                questions_path=args.questions,
                out_dir=args.out_dir,
            )
            print(json.dumps({k: report.get(k) for k in (
                "skipped", "reason", "results_json", "n_questions",
                "n_human_verified", "metrics",
            ) if k in report or k == "reason"}, indent=2, default=str))
            if report.get("skipped") and report.get("n_questions", 0) == 0 and s == "test":
                codes = 1
        return codes

    report = evaluate(
        config_name=args.config,
        split=split,
        verified_only=args.verified_only,
        questions_path=args.questions,
        out_dir=args.out_dir,
    )
    print(json.dumps({
        "skipped": report.get("skipped"),
        "reason": report.get("reason"),
        "results_json": report.get("results_json"),
        "results_md": report.get("results_md"),
        "n_questions": report.get("n_questions"),
        "n_human_verified": report.get("n_human_verified"),
        "n_draft": report.get("n_draft"),
        "corpus_hash": report.get("corpus_hash"),
        "git_commit": report.get("git_commit"),
        "metrics": report.get("metrics"),
    }, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
