"""Unit tests for gold-span → chunk relevance mapping."""

from __future__ import annotations

from evals.span_map import (
    GoldSpan,
    RetrievedChunk,
    char_overlap_ratio,
    ranks_of_relevant,
    relevant_chunk_ids,
    span_matches_chunk,
)


def test_char_overlap_containment():
    span = "The candidate name is Ada Lovelace"
    chunk = "Intro. The candidate name is Ada Lovelace. Skills follow."
    assert char_overlap_ratio(span, chunk) >= 0.5


def test_span_matches_same_page_and_file():
    gold = GoldSpan("resume.pdf", 2, "Python and SQL experience")
    chunk = RetrievedChunk("resume.pdf", 2, "She has Python and SQL experience on projects.", "d1_0")
    assert span_matches_chunk(gold, chunk, min_overlap=0.4)


def test_span_rejects_wrong_page():
    gold = GoldSpan("resume.pdf", 2, "Python and SQL experience")
    chunk = RetrievedChunk("resume.pdf", 3, "Python and SQL experience", "d1_1")
    assert not span_matches_chunk(gold, chunk, min_overlap=0.4)


def test_span_rejects_wrong_file():
    gold = GoldSpan("a.pdf", 1, "secret token ALPHA")
    chunk = RetrievedChunk("b.pdf", 1, "secret token ALPHA", "x")
    assert not span_matches_chunk(gold, chunk, min_overlap=0.4)


def test_basename_strips_upload_uuid_prefix():
    from evals.span_map import basename_key

    assert basename_key("Liyakat_DataScientist_Resume.pdf") == basename_key(
        "098d6852-69ee-4255-bdf8-1c2a5a500c46_Liyakat_DataScientist_Resume.pdf"
    )


def test_span_split_across_two_chunks():
    """A gold span that straddles two chunks should hit both when each overlaps enough."""
    gold = GoldSpan(
        "manual.pdf",
        5,
        "The flux capacitor requires 1.21 gigawatts of power for temporal displacement.",
    )
    c1 = RetrievedChunk(
        "manual.pdf",
        5,
        "Warning. The flux capacitor requires 1.21 gigawatts of power",
        "doc_0",
    )
    c2 = RetrievedChunk(
        "manual.pdf",
        5,
        "of power for temporal displacement. See appendix.",
        "doc_1",
    )
    # Each half should still overlap the full span at a modest threshold
    hits = relevant_chunk_ids([gold], [c1, c2], min_overlap=0.25)
    assert "doc_0" in hits
    assert "doc_1" in hits


def test_ranks_of_relevant_order():
    gold = [GoldSpan("a.pdf", 1, "unique marker ZZZ9")]
    chunks = [
        RetrievedChunk("a.pdf", 1, "unrelated text", "c0"),
        RetrievedChunk("a.pdf", 1, "here is unique marker ZZZ9 today", "c1"),
        RetrievedChunk("a.pdf", 1, "also unique marker ZZZ9 again", "c2"),
    ]
    ranks = ranks_of_relevant(gold, chunks, min_overlap=0.3)
    assert ranks == [2, 3]
