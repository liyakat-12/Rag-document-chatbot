"""Unit tests for hybrid search RRF fusion."""

from langchain_core.documents import Document

from backend.app.rag.hybrid_search import reciprocal_rank_fusion


def test_rrf_prefers_docs_in_both_lists():
    a = Document(page_content="alpha", metadata={"chunk_id": "a"})
    b = Document(page_content="beta", metadata={"chunk_id": "b"})
    c = Document(page_content="gamma", metadata={"chunk_id": "c"})

    dense = [(a, 0.9), (b, 0.8)]
    sparse = [(b, 5.0), (c, 4.0)]

    fused = reciprocal_rank_fusion([dense, sparse])
    assert fused[0][0].metadata["chunk_id"] == "b"
