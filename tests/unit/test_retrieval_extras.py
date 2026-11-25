"""Unit tests for BM25 tokenizer switch, exact boost, dedupe, reranker fallback."""

from __future__ import annotations

from langchain_core.documents import Document as LCDocument

from backend.app.rag.dedupe import dedupe_near_duplicates
from backend.app.rag.hybrid_search import _exact_match_boost, _tokenize_normalized, _tokenize_whitespace
from backend.app.rag.reranker import rerank_candidates


def test_whitespace_vs_normalized_tokenizer():
    text = "Exit load: 1% (code HDFC/O/E/MIF/07/04/0015)"
    ws = _tokenize_whitespace(text)
    norm = _tokenize_normalized(text)
    assert "1%" in norm
    assert any("exit" in t for t in norm)
    # whitespace keeps punctuation glued
    assert any("load:" in t or "load" in t for t in ws)


def test_exact_match_boost_prefers_code_hit():
    q = 'What is "HDFC/O/E/MIF/07/04/0015"?'
    a = LCDocument(page_content="unrelated text", metadata={"chunk_id": "a"})
    b = LCDocument(
        page_content="Scheme code HDFC/O/E/MIF/07/04/0015 appears here",
        metadata={"chunk_id": "b"},
    )
    ranked = _exact_match_boost(q, [(a, 1.0), (b, 1.0)])
    assert ranked[0][0].metadata["chunk_id"] == "b"


def test_dedupe_near_duplicates():
    d1 = LCDocument(page_content="alpha beta gamma delta " * 5, metadata={"chunk_id": "1"})
    d2 = LCDocument(page_content="alpha beta gamma delta " * 5, metadata={"chunk_id": "2"})
    d3 = LCDocument(page_content="completely different material here", metadata={"chunk_id": "3"})
    out = dedupe_near_duplicates([(d1, 1.0), (d2, 0.9), (d3, 0.8)])
    ids = [d.metadata["chunk_id"] for d, _ in out]
    assert ids == ["1", "3"]


def test_reranker_fallback_without_model(monkeypatch):
    import backend.app.rag.reranker as rr

    monkeypatch.setattr(rr, "_load_model", lambda: None)
    docs = [(LCDocument(page_content="x", metadata={"chunk_id": "1"}), 0.5)]
    out, info = rerank_candidates("q", docs)
    assert out == docs
    assert info.get("fallback") == "rrf_order"
