"""Semantic cache must not leak answers across document scopes."""

from backend.app.rag.semantic_cache import _query_hash, _scope_key, _sources_match_scope


def test_scope_key_stable_and_sorted():
    assert _scope_key(None) == "all"
    assert _scope_key([]) == "all"
    assert _scope_key(["b", "a"]) == "a,b"
    assert _scope_key(["a", "b"]) == "a,b"


def test_query_hash_differs_by_document_scope():
    q = "Who is the candidate?"
    h_all = _query_hash(q, None)
    h_a = _query_hash(q, ["doc-a"])
    h_b = _query_hash(q, ["doc-b"])
    assert h_all != h_a
    assert h_a != h_b
    assert _query_hash(q, ["doc-a"]) == h_a


def test_sources_match_scope():
    sources = [{"document_id": "doc-a", "filename": "a.pdf"}]
    assert _sources_match_scope(sources, None) is True
    assert _sources_match_scope(sources, ["doc-a"]) is True
    assert _sources_match_scope(sources, ["doc-b"]) is False
    assert _sources_match_scope([], ["doc-a"]) is False
