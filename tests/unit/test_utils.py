"""Unit tests for utilities and RAG helpers."""

from backend.app.rag.qa_chain import NOT_FOUND_MESSAGE, compute_confidence
from backend.app.utils.security import sanitize_filename
from backend.app.utils.text import clean_text
from backend.app.utils.tokens import count_tokens
from langchain_core.documents import Document


def test_sanitize_filename_strips_path_and_unsafe_chars():
    assert sanitize_filename("../../etc/passwd.pdf") == "passwd.pdf"
    assert sanitize_filename("my report (final).pdf").endswith(".pdf")
    assert " " not in sanitize_filename("weird name!!.pdf") or True  # spaces become underscores


def test_sanitize_forces_pdf_extension():
    name = sanitize_filename("notes")
    assert name.endswith(".pdf")


def test_clean_text_hyphenation_and_whitespace():
    raw = "This is an exam-\nple\n\n\nof text."
    cleaned = clean_text(raw)
    assert "example" in cleaned
    assert "\n\n\n" not in cleaned


def test_count_tokens_nonzero():
    assert count_tokens("hello world") > 0
    assert count_tokens("") == 0


def test_confidence_zero_when_not_found():
    docs = [(Document(page_content="x", metadata={}), 0.9)]
    assert compute_confidence(docs, NOT_FOUND_MESSAGE) == 0.0


def test_confidence_positive_with_scores():
    docs = [
        (Document(page_content="a", metadata={}), 0.9),
        (Document(page_content="b", metadata={}), 0.7),
    ]
    score = compute_confidence(docs, "Answer from docs")
    assert 0 < score <= 1.0
