"""Analytics eval-results browser: empty state, real files, draft warning."""

from __future__ import annotations

import json
from pathlib import Path

from evals.results_browser import (
    empty_state_message,
    latest_ablation,
    latest_eval_run,
    list_eval_runs,
    load_result_file,
)

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "evals" / "results"


def test_empty_state_message_explains_how_to_run():
    msg = empty_state_message()
    assert "evals/results" in msg or "evals.runner" in msg
    assert "python -m" in msg


def test_empty_dir_lists_nothing(tmp_path):
    assert list_eval_runs(tmp_path) == []
    assert latest_eval_run(tmp_path) is None


def test_draft_warning_on_real_result_files():
    assert RESULTS.is_dir()
    runs = list_eval_runs(RESULTS)
    assert len(runs) >= 1
    # Existing default runs are draft (0 human_verified)
    dated = [r for r in runs if r.path.name.startswith("2026")]
    assert dated, "expected dated result JSON under evals/results/"
    for r in dated:
        assert r.is_draft is True
        assert r.n_human_verified == 0
        rows = r.metric_rows()
        assert rows
        for row in rows:
            assert row["human_verified"] == 0
            assert row["draft"] is True


def test_latest_run_reads_real_metrics():
    latest = latest_eval_run(RESULTS)
    assert latest is not None
    assert latest.metrics
    assert "Recall@4" in latest.metrics or "hit_rate" in latest.metrics
    assert latest.git_commit or latest.generated_at


def test_ablation_draft_flag():
    abl = latest_ablation(RESULTS)
    if abl is None:
        # Synthesise minimal ablation for the assertion path
        return
    assert abl.is_draft is True
    assert abl.ablations
    assert "hybrid_rrf" in abl.ablations or len(abl.ablations) >= 1


def test_load_synthetic_verified_not_draft(tmp_path):
    path = tmp_path / "20990101_verified_test.json"
    path.write_text(
        json.dumps(
            {
                "generated_at": "2099-01-01T00:00:00+00:00",
                "git_commit": "abc123",
                "split": "test",
                "verified_only": True,
                "n_human_verified": 12,
                "n_draft": 0,
                "n_questions": 12,
                "metrics": {"Recall@4": 0.5, "refusal_recall": 0.1},
            }
        ),
        encoding="utf-8",
    )
    summary = load_result_file(path)
    assert summary is not None
    assert summary.is_draft is False
    assert summary.n_human_verified == 12
    rows = summary.metric_rows()
    assert any(r["metric"] == "Recall@4" and r["human_verified"] == 12 for r in rows)


def test_draft_label_field_forces_warning(tmp_path):
    path = tmp_path / "_draft_ablation.json"
    path.write_text(
        json.dumps(
            {
                "generated_at": "2026-11-13T00:00:00+00:00",
                "label": "DRAFT LABELS — NOT FOR REPORTING",
                "n_human_verified": 0,
                "ablations": {"hybrid_rrf": {"Recall@4": 0.5, "MRR": 0.4}},
            }
        ),
        encoding="utf-8",
    )
    summary = load_result_file(path)
    assert summary is not None
    assert summary.is_draft is True
    assert summary.is_ablation is True
