"""Release-1 product default (clean_chunk) snapshot lock."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SNAPSHOT = ROOT / "evals" / "results" / "_default_behaviour_snapshot.json"


@pytest.mark.slow
def test_release_default_behaviour_matches_snapshot():
    if not SNAPSHOT.is_file():
        pytest.skip(f"missing {SNAPSHOT}")
    expected = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    if expected.get("config_name") not in {"release_default", "default"}:
        pytest.skip("snapshot is not release_default yet")

    os.environ["LLM_PROVIDER"] = "extractive"
    os.environ["EMBEDDING_PROVIDER"] = "local"
    os.environ["SEMANTIC_CACHE_ENABLED"] = "false"
    os.environ["ANSWER_SENTENCE_SELECT"] = "true"
    os.environ["ANSWER_SENTENCE_SELECT_MODE"] = "clean_chunk"
    os.environ["ANSWER_SENTENCE_MAX_WORDS"] = "100"
    os.environ["ANSWER_REFUSE_ZERO_OVERLAP"] = "true"

    from backend.app.config import get_settings

    get_settings.cache_clear()

    from evals.build_behaviour_snapshot import build

    actual = asyncio.run(build(config_name="release_default"))
    assert actual["n_questions"] == expected["n_questions"]
    assert actual["corpus_hash"] == expected["corpus_hash"]

    exp_by_id = {c["id"]: c for c in expected["cases"]}
    act_by_id = {c["id"]: c for c in actual["cases"]}
    assert set(exp_by_id) == set(act_by_id)

    mismatches: list[str] = []
    for qid, exp in exp_by_id.items():
        act = act_by_id[qid]
        if act["top10_chunk_ids"] != exp["top10_chunk_ids"]:
            mismatches.append(f"{qid}: chunk_ids")
        if act["answer"] != exp["answer"]:
            mismatches.append(f"{qid}: answer")
        if act["citations"] != exp["citations"]:
            mismatches.append(f"{qid}: citations")
    assert not mismatches, "release_default changed:\n" + "\n".join(mismatches[:20])
