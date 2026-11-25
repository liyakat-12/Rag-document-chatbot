"""RRF near-tie ordering must be stable across runs."""

from __future__ import annotations

from langchain_core.documents import Document as LCDocument

from backend.app.rag.hybrid_search import reciprocal_rank_fusion


def _doc(cid: str, text: str = "x") -> LCDocument:
    return LCDocument(
        page_content=text,
        metadata={"chunk_id": cid, "filename": "a.pdf", "page_number": 1},
    )


def test_rrf_tie_break_by_dense_then_chunk_id():
    # Cross-ranked lists → identical RRF scores; dense raw scores differ
    a, b, c = _doc("chunk_a"), _doc("chunk_b"), _doc("chunk_c")
    dense = [(b, 0.90), (a, 0.50), (c, 0.40)]  # b highest FAISS
    sparse = [(a, 2.0), (b, 2.0), (c, 2.0)]  # a rank0, b rank1 → a+b equal RRF
    # a: 0.5/(k+2)+0.5/(k+1); b: 0.5/(k+1)+0.5/(k+2) → equal fused
    orders = []
    for _ in range(5):
        fused = reciprocal_rank_fusion([dense, sparse], weights=[0.5, 0.5])
        orders.append([d.metadata["chunk_id"] for d, _ in fused])
    assert len(set(tuple(o) for o in orders)) == 1
    # Equal RRF → higher dense score first → chunk_b before chunk_a
    assert orders[0][0] == "chunk_b"
    assert orders[0].index("chunk_b") < orders[0].index("chunk_a")


def test_rrf_equal_dense_breaks_by_chunk_id():
    a, b = _doc("aaa"), _doc("zzz")
    # Equal fused (cross ranks) + equal dense → lexicographic chunk_id
    fused = reciprocal_rank_fusion(
        [[(a, 0.5), (b, 0.5)], [(b, 1.0), (a, 1.0)]],
        weights=[0.5, 0.5],
    )
    ids = [d.metadata["chunk_id"] for d, _ in fused]
    assert ids[0] == "aaa"
    ids2 = [
        d.metadata["chunk_id"]
        for d, _ in reciprocal_rank_fusion(
            [[(a, 0.5), (b, 0.5)], [(b, 1.0), (a, 1.0)]],
            weights=[0.5, 0.5],
        )
    ]
    assert ids == ids2


def test_rrf_stable_across_repeated_calls():
    docs = [_doc(f"id_{i:03d}") for i in range(6)]
    dense = [(docs[i], 0.9 - i * 0.05) for i in range(6)]
    sparse = [(docs[5 - i], 3.0 - i) for i in range(6)]
    first = [d.metadata["chunk_id"] for d, _ in reciprocal_rank_fusion([dense, sparse])]
    for _ in range(10):
        again = [d.metadata["chunk_id"] for d, _ in reciprocal_rank_fusion([dense, sparse])]
        assert again == first
