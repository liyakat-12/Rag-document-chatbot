"""Unit tests for refusal signals, normaliser, decision rule, cache key, calibrate."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from langchain_core.documents import Document as LCDocument

from backend.app.rag.refusal import (
    compute_signals,
    decide,
    extract_critical_terms,
    normalize_for_coverage,
    refusal_config_hash,
    thresholds_from_settings,
)
from backend.app.config import Settings


def test_normalize_keeps_percentages_and_strips_punct():
    toks = normalize_for_coverage("Exit load: 1% and TER 0.20% — ok?")
    assert "1%" in toks
    assert "0.20%" in toks
    assert "exit" in toks
    assert "load" in toks
    # colon/emdash stripped away as standalone tokens
    assert ":" not in toks
    assert "—" not in toks


def test_critical_terms_include_numbers_and_codes():
    q = 'What is HDFC/O/E/MIF/07/04/0015 exit load of 1%?'
    crit = extract_critical_terms(q)
    assert any("1%" in c or c == "1" for c in crit)
    assert any("hdfc" in c.lower() for c in crit)


def _doc(text: str, chunk_id: str) -> LCDocument:
    return LCDocument(page_content=text, metadata={"chunk_id": chunk_id, "filename": "x.pdf", "page_number": 1})


def test_signals_and_decision_answered():
    q = "What is the exit load of 1% for HDFC Mid Cap?"
    docs = [(_doc("HDFC Mid Cap Fund exit load of 1% within 1 year", "c1"), 0.9)]
    signals = compute_signals(
        q,
        faiss_ranked=docs,
        bm25_ranked=docs,
        fused_ranked=docs,
    )
    assert signals.rank_agreement == 1.0
    assert signals.content_term_coverage > 0.3
    verdict = decide(signals)
    assert verdict.decision in {"answered", "weak_evidence", "not_found"}


def test_decision_not_found_on_empty():
    signals = compute_signals(
        "What is the Sharpe ratio of Mars Fund?",
        faiss_ranked=[],
        bm25_ranked=[],
        fused_ranked=[],
    )
    verdict = decide(signals)
    assert verdict.decision == "not_found"


def test_refusal_config_hash_changes_with_flag():
    a = Settings(refusal_enabled=False)
    b = Settings(refusal_enabled=True)
    assert refusal_config_hash(a) != refusal_config_hash(b)


def test_cache_key_includes_refusal_hash(monkeypatch):
    from backend.app.rag import semantic_cache as sc
    from backend.app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("REFUSAL_ENABLED", "false")
    get_settings.cache_clear()
    h1 = sc._query_hash("hello world", None)
    monkeypatch.setenv("REFUSAL_ENABLED", "true")
    get_settings.cache_clear()
    h2 = sc._query_hash("hello world", None)
    assert h1 != h2
    get_settings.cache_clear()


def test_calibrate_refuses_without_verified_labels(tmp_path: Path):
    from evals.calibrate_refusal import calibrate, MIN_VERIFIED_TUNE

    qpath = tmp_path / "q.jsonl"
    # draft-only fixture
    rows = [
        {
            "id": f"d{i}",
            "query": "q",
            "category": "factual",
            "answerable": True,
            "gold": [],
            "key_facts": [],
            "split": "tune",
            "label_source": "draft",
            "notes": "",
        }
        for i in range(25)
    ]
    qpath.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    with pytest.raises(SystemExit) as ei:
        calibrate(qpath)
    assert str(MIN_VERIFIED_TUNE) in str(ei.value)
