"""Tests for advanced query rewriting and cross-encoder reranking."""

from types import SimpleNamespace

import pytest
from langchain_core.documents import Document

from backend.app.rag import advanced_retrieval as advanced


def test_parse_query_variants_keeps_original_and_deduplicates():
    result = advanced._parse_query_variants(
        "- VPN troubleshooting steps\n- VPN troubleshooting steps\n2. Remote access issue",
        "vpn not working wfh",
        3,
    )
    assert result == [
        "vpn not working wfh",
        "VPN troubleshooting steps",
        "Remote access issue",
    ]


def test_extractive_query_variants_keep_original():
    result = advanced._extractive_query_variants(
        "How can I troubleshoot VPN connection issues while working remotely?",
        3,
    )
    assert result[0].startswith("How can I troubleshoot")
    assert len(result) >= 2
    assert "VPN" in result[1]


@pytest.mark.asyncio
async def test_rewrite_query_uses_keyword_fallback_without_llm(monkeypatch):
    monkeypatch.setattr(
        advanced,
        "get_settings",
        lambda: SimpleNamespace(
            query_rewriting_enabled=True,
            query_rewrite_max_variants=3,
            llm_provider="extractive",
        ),
    )
    question = "How can I troubleshoot VPN connection issues while working remotely?"
    variants, details = await advanced.rewrite_query(question)

    assert variants[0] == question
    assert len(variants) >= 2
    assert details["method"] == "keyword_fallback"


def test_reranker_disabled_preserves_rrf_order(monkeypatch):
    monkeypatch.setattr(
        advanced,
        "get_settings",
        lambda: SimpleNamespace(reranker_enabled=False, retriever_top_k=2),
    )
    docs = [
        (Document(page_content="first", metadata={"chunk_id": "1"}), 0.9),
        (Document(page_content="second", metadata={"chunk_id": "2"}), 0.8),
    ]

    ranked, details = advanced.rerank_documents("question", docs)

    assert [doc.metadata["chunk_id"] for doc, _ in ranked] == ["1", "2"]
    assert details["enabled"] is False


def test_cross_encoder_reranks_by_relevance(monkeypatch):
    class FakeCrossEncoder:
        def predict(self, pairs, show_progress_bar=False):
            return [0.1, 0.9]

    monkeypatch.setattr(
        advanced,
        "get_settings",
        lambda: SimpleNamespace(
            reranker_enabled=True,
            retriever_top_k=2,
            reranker_model="fake-model",
            reranker_max_length=128,
        ),
    )
    monkeypatch.setattr(advanced, "_get_cross_encoder", lambda: FakeCrossEncoder())
    docs = [
        (Document(page_content="less relevant", metadata={"chunk_id": "1"}), 0.9),
        (Document(page_content="more relevant", metadata={"chunk_id": "2"}), 0.8),
    ]

    ranked, details = advanced.rerank_documents("question", docs)

    assert [doc.metadata["chunk_id"] for doc, _ in ranked] == ["2", "1"]
    assert details["method"] == "cross_encoder"
