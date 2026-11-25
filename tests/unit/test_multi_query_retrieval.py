"""Tests for opt-in multi-query RRF and final reranking."""

from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from backend.app.rag import qa_chain
from backend.app.rag.hybrid_search import HybridSearchResult


def _doc(chunk_id: str):
    return Document(page_content=f"content for {chunk_id}", metadata={"chunk_id": chunk_id})


@pytest.mark.asyncio
async def test_multi_query_disabled_keeps_release_baseline(monkeypatch):
    baseline = HybridSearchResult(results=[(_doc("baseline"), 1.0)])
    monkeypatch.setattr(
        qa_chain, "get_settings",
        lambda: SimpleNamespace(retrieval_multi_query_enabled=False),
    )
    calls = []
    monkeypatch.setattr(
        qa_chain, "hybrid_search_detailed",
        lambda question, document_ids=None: calls.append(question) or baseline,
    )

    result = await qa_chain.retrieve_detailed("original question")

    assert result is baseline
    assert calls == ["original question"]


@pytest.mark.asyncio
async def test_multi_query_fuses_candidate_rankings(monkeypatch):
    a, b, c = _doc("a"), _doc("b"), _doc("c")
    settings = SimpleNamespace(
        retrieval_multi_query_enabled=True,
        retrieval_multi_query_max_variants=3,
        retrieval_multi_query_candidate_multiplier=2,
        retriever_top_k=2,
        retrieval_reranker_enabled=False,
        retrieval_reranker_top_n=16,
        retrieval_dedupe_near_duplicates=False,
    )
    monkeypatch.setattr(qa_chain, "get_settings", lambda: settings)

    async def fake_rewrites(question, recent_history="", max_variants=None):
        return [question, "alternate wording"], {"enabled": True, "method": "test", "variants": 2}

    monkeypatch.setattr(qa_chain, "generate_query_variants", fake_rewrites)
    calls = []

    def fake_hybrid(query, k=None, document_ids=None, **kwargs):
        calls.append((query, k, kwargs))
        if query == "original question":
            return HybridSearchResult(
                results=[(a, 1.0), (b, 0.8)],
                details={"latency_ms": 1, "semantic": {"count": 2}, "bm25": {"count": 1}},
                dense_results=[(a, 1.0)],
                sparse_results=[(b, 2.0)],
            )
        return HybridSearchResult(
            results=[(b, 1.0), (c, 0.8)],
            details={"latency_ms": 2, "semantic": {"count": 2}, "bm25": {"count": 1}},
            dense_results=[(b, 1.0)],
            sparse_results=[(c, 2.0)],
        )

    monkeypatch.setattr(qa_chain, "hybrid_search_detailed", fake_hybrid)

    result = await qa_chain.retrieve_detailed("original question", document_ids=["doc-1"])

    assert [doc.metadata["chunk_id"] for doc, _ in result.results] == ["b", "a"]
    assert result.details["strategy"] == "multi_query_hybrid_rrf"
    assert result.details["query_variants"] == ["original question", "alternate wording"]
    assert result.details["candidate_count"] == 3
    assert result.dense_results[0][0].metadata["chunk_id"] == "a"
    assert len(calls) == 2
    assert all(call[1] == 4 for call in calls)
    assert all(call[2]["apply_reranker"] is False for call in calls)
    assert all(call[2]["record_metrics"] is False for call in calls)


@pytest.mark.asyncio
async def test_multi_query_runs_existing_cross_encoder_once_after_fusion(monkeypatch):
    a, b, c = _doc("a"), _doc("b"), _doc("c")
    settings = SimpleNamespace(
        retrieval_multi_query_enabled=True,
        retrieval_multi_query_max_variants=2,
        retrieval_multi_query_candidate_multiplier=2,
        retriever_top_k=2,
        retrieval_reranker_enabled=True,
        retrieval_reranker_top_n=8,
        retrieval_dedupe_near_duplicates=False,
    )
    monkeypatch.setattr(qa_chain, "get_settings", lambda: settings)

    async def fake_rewrites(question, recent_history="", max_variants=None):
        return [question, "alternate"], {"enabled": True, "method": "test", "variants": 2}

    monkeypatch.setattr(qa_chain, "generate_query_variants", fake_rewrites)

    def fake_hybrid(query, k=None, document_ids=None, **kwargs):
        docs = [(a, 1.0), (b, 0.8)] if query == "query" else [(b, 1.0), (c, 0.8)]
        return HybridSearchResult(results=docs, details={}, dense_results=[], sparse_results=[])

    monkeypatch.setattr(qa_chain, "hybrid_search_detailed", fake_hybrid)
    rerank_calls = []

    def fake_rerank(question, candidates):
        rerank_calls.append((question, len(candidates)))
        return [(c, 0.9), (b, 0.6), (a, 0.1)], {
            "enabled": True, "fallback": None, "model": "test-cross-encoder"
        }

    import backend.app.rag.reranker as reranker
    monkeypatch.setattr(reranker, "rerank_candidates", fake_rerank)

    result = await qa_chain.retrieve_detailed("query")

    assert rerank_calls == [("query", 3)]
    assert result.results[0][0].metadata["chunk_id"] == "c"
    assert result.details["reranker"]["model"] == "test-cross-encoder"
