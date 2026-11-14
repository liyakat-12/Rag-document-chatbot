"""Sentence-select extractive answers + hyphenation fix."""

from __future__ import annotations

from langchain_core.documents import Document as LCDocument

from backend.app.rag.sentence_select import (
    highlight_sentences_in_chunk,
    is_contact_line,
    select_answer_sentences,
    split_into_sentences,
)
from backend.app.utils.text import clean_text, fix_hyphenation


def test_split_bullets_and_pipes():
    text = "Alpha fact one. • Beta bullet two | Gamma pipe three. Delta four!"
    parts = split_into_sentences(text)
    assert any("Alpha" in p for p in parts)
    assert any("Beta" in p for p in parts)
    assert any("Gamma" in p for p in parts)


def test_drop_contact_unless_asked():
    docs = [
        (
            LCDocument(
                page_content=(
                    "HDFC Mid Cap Fund invests predominantly in mid-cap stocks. "
                    "Contact: founder@example.com | LinkedIn | Github "
                    "Phone +91 98765 43210. "
                    "The scheme code is HDFC/O/E/MIF/07/04/0015 on the cover."
                ),
                metadata={
                    "filename": "sid_hdfc_midcap.pdf",
                    "page_number": 1,
                    "chunk_id": "c1",
                    "document_id": "d1",
                },
            ),
            0.9,
        )
    ]
    assert is_contact_line("Email me at founder@example.com today please.")
    result = select_answer_sentences(
        "What is the scheme code for HDFC Mid Cap Fund?",
        docs,
        use_embeddings=False,
    )
    joined = " ".join(s.text for s in result.sentences).lower()
    assert "scheme code" in joined or "hdfc" in joined
    assert "example.com" not in joined
    assert "linkedin" not in joined
    assert result.word_count <= 60


def test_contact_kept_when_question_asks():
    docs = [
        (
            LCDocument(
                page_content="Reach the AMC at support@hdfcfund.com for SID queries.",
                metadata={
                    "filename": "sid_hdfc_midcap.pdf",
                    "page_number": 2,
                    "chunk_id": "c2",
                    "document_id": "d1",
                },
            ),
            0.8,
        )
    ]
    result = select_answer_sentences(
        "What email contact is listed?",
        docs,
        use_embeddings=False,
    )
    assert any("@" in s.text for s in result.sentences) or "@" in result.answer


def test_document_order_and_citations():
    docs = [
        (
            LCDocument(
                page_content="First document sentence about Motilal Oswal Midcap Fund benchmark.",
                metadata={
                    "filename": "sid_motilal_midcap.pdf",
                    "page_number": 1,
                    "chunk_id": "a",
                    "document_id": "1",
                },
            ),
            0.5,
        ),
        (
            LCDocument(
                page_content="Second document sentence about Motilal Oswal Midcap Fund exit load.",
                metadata={
                    "filename": "sid_motilal_midcap.pdf",
                    "page_number": 5,
                    "chunk_id": "b",
                    "document_id": "1",
                },
            ),
            0.9,
        ),
    ]
    result = select_answer_sentences(
        "Motilal Oswal Midcap Fund benchmark and exit load?",
        docs,
        use_embeddings=False,
    )
    assert result.sentences
    orders = [s.doc_order for s in result.sentences]
    assert orders == sorted(orders)
    cites = result.citation_dicts()
    assert all(c.get("filename") for c in cites)
    assert all(c.get("page_number") for c in cites)


def test_highlight_in_chunk_not_verbatim_dump():
    chunk = "Alpha. Selected midcap sentence here. Omega."
    marked = highlight_sentences_in_chunk(chunk, ["Selected midcap sentence here."])
    assert ">>>Selected midcap sentence here.<<<" in marked
    assert marked != "Selected midcap sentence here."


def test_fix_hyphenation_hands_on_and_linebreak():
    raw = "hands -on training and capitalisa-\ntion norms"
    fixed = fix_hyphenation(raw)
    assert "hands-on" in fixed
    assert "capitalisation" in fixed
    # Flag off path (default clean_text) still joins line-break only
    legacy = clean_text("exam-\nple hands -on", fix_hyphens=False)
    assert "example" in legacy
    # Flag on
    strong = clean_text("hands -on lab", fix_hyphens=True)
    assert "hands-on" in strong
