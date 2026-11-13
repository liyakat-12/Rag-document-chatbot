"""Labeling helper critical-term scan (no interactive input)."""

from __future__ import annotations

from evals.label import _critical_terms_for_label, scan_corpus_for_critical_terms


def test_critical_terms_include_codes_and_numbers():
    terms = _critical_terms_for_label(
        "Does SEBI/HO/IMD/IMD-PoD-2/P/CIR/2024/30 assign a 1% TER to HDFC Mid Cap?"
    )
    assert any("1%" in t or t == "1" for t in terms)
    assert any("hdfc" in t for t in terms)


def test_scan_returns_structured_hits_or_absence():
    lines = scan_corpus_for_critical_terms(
        "What ISIN does the HDFC Mid Cap Fund SID print on page 1?"
    )
    assert lines
    assert any("Critical terms" in ln for ln in lines)
    # Either hits or explicit absence note
    assert any("HIT" in ln or "no critical-term hits" in ln for ln in lines)
