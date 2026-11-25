"""Integration-level tests for advanced query fusion and final reranking."""

from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from backend.app.rag import advanced_retrieval as advanced
from backend.app.rag.hybrid_search import HybridSearchResult


def _doc(key: str) -> Document:
    return Document(page_content=f"evidence {key}", metadata={"chunk_id": key})


@pytest.mark.asyncio
async def test_advanced_retrieval_fuses_variants_then_reranks_once(monkeypatch):
    a, b, c = _doc("a"), _doc("b"), _doc("c")
    settings = SimpleNamespace(
        query_rewriting_enabled=True,
        query_rewrite_max_variants=3,
        reranker_enabled=True,
        reranker_model="test-cross-encoder",
        reranker_candidate_multiplier=3,
        reranker_max_length=128,
        retriever_top_k=2,
        hybrid_search_weight=0.5,
        retrieval_dedupe_near_duplicates=False,
    )
    monkeypatch.setattr(advanced, "get_settings", lambda: settings)

    async def fake_rewrite(question, recent_history="", max_variants=None):
        return [question, "alternate query"], {
            "enabled": True, "method": "test", "variants": 2, "latency_ms": 0.1
        }

    monkeypatch.setattr(advanced, "rewrite_query", fake_rewrite)

    def fake_hybrid(query, k=None, document_ids=None):
        if query == "original":
            return HybridSearchResult(results=[(a, 0.9), (b, 0.8)], details={})
        return HybridSearchResult(results=[(b, 0.9), (c, 0.8)], details={})

    import backend.app.rag.hybrid_search as hybrid
    monkeypatch.setattr(hybrid, "hybrid_search_detailed", fake_hybrid)

    rerank_calls = []

    def fake_rerank(question, candidates, top_k=None):
        rerank_calls.append((question, len(candidates), top_k))
        # Deliberately move C above the RRF leader to prove reranking is applied.
        return [(c, 2.0), (b, 1.0)], {
            "enabled": True,
            "method": "cross_encoder",
            "model": "test-cross-encoder",
            "candidate_count": len(candidates),
            "reranked_count": 2,
        }

    monkeypatch.setattr(advanced, "rerank_documents", fake_rerank)

    result = await advanced.retrieve_advanced("original", document_ids=["doc-1"])

    assert rerank_calls == [("original", 3, 2)]
    assert [doc.metadata["chunk_id"] for doc, _ in result.results] == ["c", "b"]
    assert result.details["query_variants"] == ["original", "alternate query"]
    assert result.details["candidate_count"] == 3
    assert result.details["reranking"]["method"] == "cross_encoder"
    assert result.details["strategy"] == "advanced_hybrid_rrf_rerank"
