"""Ingest quality flags: repeated headers/footers and low-text pages."""

from __future__ import annotations

from langchain_core.documents import Document as LCDocument

from backend.app.rag.ingest import (
    detect_repeated_header_footer_lines,
    flag_low_text_pages,
    strip_repeated_headers_footers,
)
from evals.eval_index import chunking_config_hash


def _pages(texts: list[str]) -> list[LCDocument]:
    out = []
    for i, t in enumerate(texts):
        out.append(LCDocument(page_content=t, metadata={"page": i}))
    return out


def test_detect_repeated_header_on_synthetic_multipage():
    header = "SID of Motilal Oswal Midcap Fund"
    pages = [
        f"{header}\nBody content page {i} with unique facts about scheme {i}.\nFooter {i}"
        for i in range(8)
    ]
    repeated = detect_repeated_header_footer_lines(pages, min_pages=3, min_fraction=0.4)
    assert header in repeated


def test_strip_removes_header_keeps_body():
    header = "SID of Motilal Oswal Midcap Fund"
    docs = _pages(
        [f"{header}\nUnique body alpha {i} details here.\nPage end {i}" for i in range(6)]
    )
    stripped, removed = strip_repeated_headers_footers(docs, min_pages=3, min_fraction=0.4)
    assert header in removed
    for d in stripped:
        assert header not in d.page_content
        assert "Unique body" in d.page_content


def test_no_removal_of_lines_appearing_once():
    pages = [
        "UniqueHeaderOnlyOnPage0\nShared body text about midcap funds.\n",
        "Different top line\nShared body text about midcap funds.\n",
        "Another opener\nShared body text about midcap funds.\n",
        "Fourth opener\nShared body text about midcap funds.\n",
        "Fifth opener\nShared body text about midcap funds.\n",
    ]
    # "Shared body..." appears on every page but is NOT an edge header/footer line
    # when it's the middle — put unique once-only at edge:
    pages = [
        "ONCE_ONLY_ALPHA\nMiddle shared content for retrieval tests.\nfoot A",
        "Top B\nMiddle shared content for retrieval tests.\nfoot B",
        "Top C\nMiddle shared content for retrieval tests.\nfoot C",
        "Top D\nMiddle shared content for retrieval tests.\nfoot D",
        "Top E\nMiddle shared content for retrieval tests.\nfoot E",
    ]
    repeated = detect_repeated_header_footer_lines(pages, min_pages=3, min_fraction=0.4)
    assert "ONCE_ONLY_ALPHA" not in repeated
    docs = _pages(pages)
    stripped, removed = strip_repeated_headers_footers(docs, min_pages=3, min_fraction=0.4)
    assert "ONCE_ONLY_ALPHA" not in removed
    assert "ONCE_ONLY_ALPHA" in stripped[0].page_content


def test_flag_low_text_pages():
    docs = _pages(
        [
            "x" * 200,  # ok
            "short",  # low
            "y" * 150,
            "ab",  # low
        ]
    )
    flagged = flag_low_text_pages(docs, char_threshold=100)
    pages = {f["page"] for f in flagged}
    assert pages == {2, 4}
    assert docs[1].metadata.get("low_text") is True
    assert docs[0].metadata.get("low_text") is False


def test_ingest_flags_change_chunking_config_hash():
    base = {
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "embedding_provider": "local",
        "local_embedding_model": "BAAI/bge-small-en-v1.5",
    }
    h0 = chunking_config_hash(base)
    h1 = chunking_config_hash({**base, "ingest_strip_repeated_headers_footers": True})
    h2 = chunking_config_hash({**base, "ingest_flag_low_text_pages": True})
    assert h0 != h1
    assert h0 != h2
    assert h1 != h2
    # Default-off equals base
    assert chunking_config_hash({**base, "ingest_strip_repeated_headers_footers": False}) == h0
