"""Fail if default retrieval + extractive answers diverge from the snapshot.

Requires evals/results/_default_behaviour_snapshot.json (built via
`python -m evals.build_behaviour_snapshot`).
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "evals" / "results" / "_default_behaviour_snapshot.json"
QUESTIONS = ROOT / "evals" / "data" / "questions.jsonl"


def _load_snapshot() -> dict:
    if not SNAPSHOT.is_file():
        pytest.skip(f"missing snapshot {SNAPSHOT}")
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


@pytest.mark.slow
def test_default_behaviour_matches_snapshot():
    """Re-run snapshot pipeline; require identical top-10 IDs, answer, citations."""
    os.environ["LLM_PROVIDER"] = "extractive"
    os.environ.setdefault("EMBEDDING_PROVIDER", "local")
    os.environ.setdefault("SEMANTIC_CACHE_ENABLED", "false")

    from backend.app.config import get_settings

    get_settings.cache_clear()

    expected = _load_snapshot()
    assert expected.get("n_questions", 0) > 0

    from evals.build_behaviour_snapshot import build

    actual = asyncio.run(build())

    assert actual["n_questions"] == expected["n_questions"]
    assert actual["corpus_hash"] == expected["corpus_hash"]

    exp_by_id = {c["id"]: c for c in expected["cases"]}
    act_by_id = {c["id"]: c for c in actual["cases"]}
    assert set(exp_by_id) == set(act_by_id)

    mismatches: list[str] = []
    for qid, exp in exp_by_id.items():
        act = act_by_id[qid]
        if act["top10_chunk_ids"] != exp["top10_chunk_ids"]:
            mismatches.append(f"{qid}: chunk_ids differ")
        if act["answer"] != exp["answer"]:
            mismatches.append(f"{qid}: answer differs")
        if act["citations"] != exp["citations"]:
            mismatches.append(f"{qid}: citations differ")

    assert not mismatches, "Default behaviour changed:\n" + "\n".join(mismatches[:20])
