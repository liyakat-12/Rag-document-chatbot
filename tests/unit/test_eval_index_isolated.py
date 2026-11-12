"""Prove the eval runner uses an isolated index, not the app FAISS/DB."""

from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def test_eval_runner_with_empty_app_store(tmp_path, monkeypatch):
    """Empty app vector_store must not be used; eval builds its own corpus index."""
    from backend.app.rag import vector_store as vs

    empty_vs = tmp_path / "app_vector_store"
    empty_vs.mkdir()
    monkeypatch.setattr(vs, "_index_path", lambda: empty_vs / "faiss_index")
    monkeypatch.setattr(vs, "_meta_path", lambda: empty_vs / "metadata.json")
    vs.reset_vector_store()

    store = vs.get_vector_store()
    assert len(getattr(store.docstore, "_dict", {})) == 0

    from evals.runner import evaluate

    questions = ROOT / "evals" / "data" / "questions.jsonl"
    if not questions.is_file() or questions.stat().st_size < 10:
        pytest.skip("questions.jsonl not ready")

    out_dir = tmp_path / "results"
    report = evaluate(
        config_name="default",
        split="test",
        verified_only=False,
        questions_path=questions,
        out_dir=out_dir,
    )
    assert report.get("uses_app_index") is False
    assert report.get("corpus_hash")
    assert report.get("chunking_config_hash")
    assert "eval_index_path" in report
    if not report.get("skipped"):
        assert report.get("indexed_chunks", 0) > 0
        assert Path(report["eval_index_path"]).exists()
        # App store still empty after eval
        assert len(getattr(vs.get_vector_store().docstore, "_dict", {})) == 0


def test_chunking_config_hash_stable():
    from evals.eval_index import chunking_config_hash

    a = chunking_config_hash(
        {"chunk_size": 1000, "chunk_overlap": 200, "embedding_provider": "local"}
    )
    b = chunking_config_hash(
        {"chunk_size": 1000, "chunk_overlap": 200, "embedding_provider": "local"}
    )
    c = chunking_config_hash(
        {"chunk_size": 800, "chunk_overlap": 200, "embedding_provider": "local"}
    )
    assert a == b
    assert a != c
