"""Citation page viewer: exact / line-break / hyphen / block / chunk fallbacks."""

from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from backend.app.rag.page_viewer import (
    find_highlight_rects,
    highlight_span_in_text,
    normalize_match_text,
    render_page_with_highlight,
)

ROOT = Path(__file__).resolve().parents[2]
REAL_MOTILAL = ROOT / "evals" / "corpus" / "real" / "sid_motilal_midcap.pdf"
REAL_HDFC = ROOT / "evals" / "corpus" / "real" / "sid_hdfc_midcap.pdf"


@pytest.fixture(scope="module")
def hyphen_pdf(tmp_path_factory) -> Path:
    """Synthetic page with a hyphenated line break: 'capitalisa-\\ntion'."""
    path = tmp_path_factory.mktemp("pdf") / "hyphen_fixture.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    # Insert text with an explicit soft hyphen break across lines
    page.insert_text((50, 80), "The scheme follows capitalisa-", fontsize=12)
    page.insert_text((50, 96), "tion norms under SEBI regulations.", fontsize=12)
    page.insert_text((50, 140), "UniqueBlockAlpha Omega Midcap Fund particulars", fontsize=11)
    doc.save(path)
    doc.close()
    return path


@pytest.fixture(scope="module")
def linebreak_pdf(tmp_path_factory) -> Path:
    """Multi-line phrase that exact search misses as one string."""
    path = tmp_path_factory.mktemp("pdf") / "linebreak_fixture.pdf"
    doc = fitz.open()
    page = doc.new_page(width=420, height=320)
    page.insert_text((40, 70), "Investors seeking long-term capital", fontsize=12)
    page.insert_text((40, 86), "appreciation with mid cap exposure", fontsize=12)
    doc.save(path)
    doc.close()
    return path


@pytest.mark.skipif(not REAL_MOTILAL.is_file(), reason="real corpus PDF missing")
def test_exact_match_real_corpus():
    doc = fitz.open(REAL_MOTILAL)
    page = doc.load_page(0)  # cover
    # Short distinctive phrase from Motilal SID cover
    span = "SCHEME INFORMATION DOCUMENT"
    result = find_highlight_rects(page, span)
    doc.close()
    assert result.match_mode == "exact"
    assert len(result.rects) >= 1


@pytest.mark.skipif(not REAL_HDFC.is_file(), reason="real corpus PDF missing")
def test_render_real_corpus_page_cached(tmp_path, monkeypatch):
    from backend.app.rag import page_viewer as pv

    monkeypatch.setattr(pv, "page_cache_dir", lambda: tmp_path / "cache")
    (tmp_path / "cache").mkdir()
    r1 = render_page_with_highlight(
        REAL_HDFC, 1, span="SCHEME INFORMATION DOCUMENT", cache=True
    )
    assert r1.png_bytes[:8] == b"\x89PNG\r\n\x1a\n"
    assert r1.match_mode in {"exact", "normalized", "block"}
    r2 = render_page_with_highlight(
        REAL_HDFC, 1, span="SCHEME INFORMATION DOCUMENT", cache=True
    )
    assert r2.cache_hit is True
    assert r2.png_bytes == r1.png_bytes


def test_line_broken_normalized_match(linebreak_pdf, monkeypatch):
    doc = fitz.open(linebreak_pdf)
    page = doc.load_page(0)
    # PyMuPDF search_for is whitespace-tolerant; force exact path to miss so
    # the normaliser + word-box mapper is exercised.
    monkeypatch.setattr(page, "search_for", lambda *a, **k: [])
    span = "long-term capital appreciation with mid cap"
    result = find_highlight_rects(page, span)
    doc.close()
    assert result.match_mode == "normalized"
    assert len(result.rects) >= 1


def test_hyphenated_match(hyphen_pdf):
    doc = fitz.open(hyphen_pdf)
    page = doc.load_page(0)
    span = "capitalisation norms under SEBI"
    assert normalize_match_text("capitalisa-\ntion") == "capitalisation"
    result = find_highlight_rects(page, span)
    doc.close()
    assert result.match_mode in {"normalized", "block", "exact"}
    assert len(result.rects) >= 1 or result.match_mode == "chunk_fallback"


def test_block_fallback(hyphen_pdf):
    doc = fitz.open(hyphen_pdf)
    page = doc.load_page(0)
    # Paraphrase overlapping UniqueBlock tokens but not exact page string
    span = "UniqueBlockAlpha Midcap Fund scheme particulars table row"
    result = find_highlight_rects(page, span)
    doc.close()
    assert result.match_mode in {"block", "normalized"}
    if result.match_mode == "block":
        assert len(result.rects) == 1
        assert "UniqueBlockAlpha" in result.block_text


def test_chunk_text_fallback():
    chunk = "Alpha beta gamma delta epsilon zeta"
    marked = highlight_span_in_text(chunk, "gamma delta")
    assert ">>>gamma delta<<<" in marked


def test_chunk_fallback_mode_when_span_absent(hyphen_pdf):
    doc = fitz.open(hyphen_pdf)
    page = doc.load_page(0)
    result = find_highlight_rects(page, "ZZZ_NO_SUCH_TOKEN_ANYWHERE_ON_PAGE_999")
    doc.close()
    assert result.match_mode == "chunk_fallback"
    assert result.rects == []


@pytest.mark.skipif(not REAL_MOTILAL.is_file(), reason="real corpus PDF missing")
def test_normalized_on_real_multiline_header():
    """Whitespace-normalised match against Motilal repeated header wording."""
    doc = fitz.open(REAL_MOTILAL)
    # Page 2 often has running header
    page = doc.load_page(min(1, doc.page_count - 1))
    span = "SID of Motilal Oswal Midcap Fund"
    result = find_highlight_rects(page, span)
    doc.close()
    assert result.match_mode in {"exact", "normalized", "block"}
    if result.match_mode != "chunk_fallback":
        assert len(result.rects) >= 1
