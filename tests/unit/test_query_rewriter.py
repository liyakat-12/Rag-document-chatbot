"""Unit tests for bounded query rewriting."""

from types import SimpleNamespace

import pytest

from backend.app.rag import query_rewriter


def test_parser_keeps_original_deduplicates_and_respects_limit():
    variants = query_rewriter.parse_query_variants(
        "- VPN troubleshooting guide\n- VPN troubleshooting guide\n3. Remote access policy",
        "VPN not working WFH",
        max_variants=3,
    )
    assert variants == [
        "VPN not working WFH",
        "VPN troubleshooting guide",
        "Remote access policy",
    ]


def test_parser_returns_only_original_when_limit_is_one():
    assert query_rewriter.parse_query_variants(
        "- another query", "original question", max_variants=1
    ) == ["original question"]


def test_keyword_variant_preserves_technical_terms_and_codes():
    rewritten = query_rewriter.keyword_query_variant(
        "What is the VPN policy for HDFC/O/E/MIF/07/04/0015 and 10% fees?"
    )
    assert "VPN" in rewritten
    assert "HDFC/O/E/MIF/07/04/0015" in rewritten
    assert "10%" in rewritten


@pytest.mark.asyncio
async def test_extractive_mode_uses_keyword_fallback(monkeypatch):
    monkeypatch.setattr(
        query_rewriter,
        "get_settings",
        lambda: SimpleNamespace(
            retrieval_multi_query_max_variants=3,
            llm_provider="extractive",
        ),
    )

    variants, details = await query_rewriter.generate_query_variants(
        "What is the VPN policy for working from home?"
    )

    assert variants[0] == "What is the VPN policy for working from home?"
    assert len(variants) == 2
    assert "VPN" in variants[1]
    assert details["method"] == "keyword_fallback"
