"""Load and summarise evals/results/*.json for the Analytics UI (no Streamlit)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RESULTS_DIR = ROOT / "evals" / "results"

_DATE_PREFIX = re.compile(r"^(\d{8})_")
_SKIP_NAMES = {
    "_default_behaviour_snapshot.json",
    "_ingest_audit_real.json",
}


@dataclass
class EvalRunSummary:
    path: Path
    generated_at: str = ""
    git_commit: str = ""
    split: str = ""
    n_human_verified: int = 0
    n_draft: int = 0
    n_questions: int = 0
    metrics: dict[str, Any] = field(default_factory=dict)
    is_draft: bool = True
    is_ablation: bool = False
    ablations: dict[str, Any] = field(default_factory=dict)
    label: str = ""
    run_date: Optional[date] = None
    kind: str = "eval"  # eval | ablation | other

    def metric_rows(self) -> list[dict[str, Any]]:
        """Flatten headline metrics with human_verified count attached (no samples)."""
        rows = []
        skip = {"notes", "latency", "cases"}
        for key, val in (self.metrics or {}).items():
            if key in skip or isinstance(val, (dict, list)):
                continue
            rows.append(
                {
                    "metric": key,
                    "value": val,
                    "human_verified": self.n_human_verified,
                    "draft": self.is_draft,
                }
            )
        # Refusal-oriented aliases if present
        for key in (
            "not_found_accuracy",
            "refusal_precision",
            "refusal_recall",
            "false_refusal_rate",
        ):
            if key in (self.metrics or {}) and not any(r["metric"] == key for r in rows):
                rows.append(
                    {
                        "metric": key,
                        "value": self.metrics.get(key),
                        "human_verified": self.n_human_verified,
                        "draft": self.is_draft,
                    }
                )
        # Citation validity if present
        for key in ("citation_precision", "citation_recall", "valid_citation_share"):
            if key in (self.metrics or {}):
                if not any(r["metric"] == key for r in rows):
                    rows.append(
                        {
                            "metric": key,
                            "value": self.metrics.get(key),
                            "human_verified": self.n_human_verified,
                            "draft": self.is_draft,
                        }
                    )
        return rows


def _parse_run_date(name: str, generated_at: str) -> Optional[date]:
    m = _DATE_PREFIX.match(name)
    if m:
        try:
            return datetime.strptime(m.group(1), "%Y%m%d").date()
        except ValueError:
            pass
    if generated_at:
        try:
            return datetime.fromisoformat(generated_at.replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None


def load_result_file(path: Path) -> Optional[EvalRunSummary]:
    if not path.is_file() or path.suffix.lower() != ".json":
        return None
    if path.name in _SKIP_NAMES:
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None

    is_ablation = "ablations" in data or path.name.startswith("_draft_ablation")
    n_verified = int(data.get("n_human_verified") or 0)
    n_draft = int(data.get("n_draft") or 0)
    label = str(data.get("label") or "")
    verified_only = bool(data.get("verified_only"))
    is_draft = (
        (not verified_only and n_verified == 0)
        or n_draft > 0
        or "DRAFT" in label.upper()
        or is_ablation
    )
    metrics = data.get("metrics") if isinstance(data.get("metrics"), dict) else {}
    if is_ablation and not metrics:
        # Surface ablation table values as metrics of the hybrid_rrf row if present
        metrics = {}

    summary = EvalRunSummary(
        path=path,
        generated_at=str(data.get("generated_at") or ""),
        git_commit=str(data.get("git_commit") or "")[:12],
        split=str(data.get("split") or ""),
        n_human_verified=n_verified,
        n_draft=n_draft,
        n_questions=int(data.get("n_questions") or data.get("n_answerable") or 0),
        metrics=metrics,
        is_draft=is_draft,
        is_ablation=is_ablation,
        ablations=data.get("ablations") if isinstance(data.get("ablations"), dict) else {},
        label=label,
        run_date=_parse_run_date(path.name, str(data.get("generated_at") or "")),
        kind="ablation" if is_ablation else "eval",
    )
    return summary


def list_eval_runs(
    results_dir: Path | None = None,
    *,
    after: date | None = None,
    before: date | None = None,
) -> list[EvalRunSummary]:
    root = results_dir or DEFAULT_RESULTS_DIR
    if not root.is_dir():
        return []
    runs: list[EvalRunSummary] = []
    for path in sorted(root.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        summary = load_result_file(path)
        if summary is None:
            continue
        if after and summary.run_date and summary.run_date < after:
            continue
        if before and summary.run_date and summary.run_date > before:
            continue
        runs.append(summary)
    return runs


def latest_eval_run(results_dir: Path | None = None) -> Optional[EvalRunSummary]:
    for run in list_eval_runs(results_dir):
        if run.kind == "eval" and not run.path.name.startswith("_"):
            return run
    # Fall back to any non-ablation
    for run in list_eval_runs(results_dir):
        if run.kind == "eval":
            return run
    return None


def latest_ablation(results_dir: Path | None = None) -> Optional[EvalRunSummary]:
    for run in list_eval_runs(results_dir):
        if run.is_ablation:
            return run
    return None


def empty_state_message() -> str:
    return (
        "No evaluation results yet. From the repo root run:\n\n"
        "`python -m evals.runner --split test`\n\n"
        "Ablations: `python -m evals.ablation_runner`\n\n"
        "JSON reports are written under `evals/results/`."
    )
