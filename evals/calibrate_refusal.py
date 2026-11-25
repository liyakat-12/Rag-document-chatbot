"""Search refusal thresholds on the *verified* tune split.

Refuses to run unless at least 20 human_verified tune questions exist.
Do not call this against draft labels for headline reporting.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

MIN_VERIFIED_TUNE = 20


def count_verified_tune(questions_path: Path) -> int:
    from evals.schema import load_questions

    qs = load_questions(questions_path)
    return sum(
        1
        for q in qs
        if q.split == "tune" and q.label_source == "human_verified"
    )


def calibrate(questions_path: Path) -> dict:
    n = count_verified_tune(questions_path)
    if n < MIN_VERIFIED_TUNE:
        raise SystemExit(
            f"calibrate_refusal: need ≥{MIN_VERIFIED_TUNE} human_verified tune "
            f"questions; found {n}. Refusing to run."
        )
    # Placeholder body — full grid search lands after human verification (Phase 2).
    return {
        "status": "ready_but_not_implemented_grid",
        "verified_tune": n,
        "note": "UNCALIBRATED — implement grid search after labels exist",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--questions",
        default=str(ROOT / "evals" / "data" / "questions.jsonl"),
    )
    args = parser.parse_args(argv)
    result = calibrate(Path(args.questions))
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
