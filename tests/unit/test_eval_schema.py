"""Schema load/filter tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evals.schema import Question, filter_questions, load_questions, write_questions


def test_roundtrip(tmp_path: Path):
    path = tmp_path / "q.jsonl"
    qs = [
        Question(
            id="t1",
            query="What is X?",
            category="factual",
            answerable=True,
            gold=[{"filename": "a.pdf", "page": 1, "span": "X is 1"}]  # type: ignore[arg-type]
            if False
            else [],
            split="tune",
            label_source="draft",
        )
    ]
    # fix gold properly
    from evals.schema import GoldItem

    qs = [
        Question(
            id="t1",
            query="What is X?",
            category="factual",
            answerable=True,
            gold=[GoldItem("a.pdf", 1, "X is 1")],
            key_facts=["X"],
            split="tune",
            label_source="draft",
        ),
        Question(
            id="u1",
            query="Mars revenue?",
            category="unanswerable_out_of_domain",
            answerable=False,
            gold=[],
            split="test",
            label_source="draft",
        ),
    ]
    write_questions(path, qs)
    loaded = load_questions(path)
    assert len(loaded) == 2
    assert filter_questions(loaded, split="test")[0].id == "u1"
    assert filter_questions(loaded, verified_only=True) == []


def test_invalid_category(tmp_path: Path):
    path = tmp_path / "bad.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "x",
                "query": "q",
                "category": "not_a_real_category",
                "answerable": True,
                "gold": [],
                "split": "test",
                "label_source": "draft",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="invalid category"):
        load_questions(path)
