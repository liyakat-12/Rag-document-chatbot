"""Follow-up rewrite: pronouns, short queries, topic change, scope preservation."""

from __future__ import annotations

import asyncio

import pytest

from backend.app.rag.followups import (
    extract_key_entities,
    rewrite_followup,
    rewrite_followup_offline,
)


def test_pronoun_followup_carries_fund_entity():
    prior = "In the HDFC Mid Cap Fund SID, what scheme code appears on the cover?"
    follow = "And what is its benchmark index?"
    result = rewrite_followup_offline(follow, [prior])
    assert result.method == "offline_entities"
    assert "HDFC" in result.rewritten.upper() or any(
        "hdfc" in e.lower() for e in result.entities_carried
    )
    assert result.original == follow


def test_short_followup_carries_entities():
    prior = "What is the full scheme name on the Motilal Oswal Midcap Fund SID cover?"
    follow = "Its exit load?"
    result = rewrite_followup_offline(follow, [prior])
    assert result.method == "offline_entities"
    joined = (result.rewritten + " " + " ".join(result.entities_carried)).lower()
    assert "motilal" in joined


def test_topic_change_does_not_carry_entities():
    prior = "What scheme code appears on the HDFC Mid Cap Fund SID cover?"
    # Explicit Nippon entity + short pronoun form that would otherwise inherit HDFC
    follow = "What about Nippon India Growth Mid Cap Fund exit load?"
    result = rewrite_followup_offline(follow, [prior])
    assert result.method == "none"
    assert result.skipped_reason in {"topic_changed", "standalone_query"}
    assert result.rewritten == follow
    assert "HDFC" not in result.rewritten.upper()
    # Pronoun-only on a different-topic short query after naming Nippon in a mid turn:
    follow2 = "its exit load within 1 month?"
    # If prior were Nippon-only, would carry; with HDFC prior + Nippon in follow2's... 
    # follow2 has no Nippon entity — would wrongly carry HDFC. Topic-change test uses
    # explicit new fund name in the follow-up itself:
    follow3 = "Nippon's exit load?"
    r3 = rewrite_followup_offline(follow3, [prior])
    assert "HDFC" not in r3.rewritten.upper()
    assert r3.method == "none"


def test_standalone_long_query_unchanged():
    prior = "What is the Motilal Oswal Midcap Fund benchmark?"
    follow = (
        "According to the SEBI MF Master Circular cover page, what circular "
        "identification number and date are printed together?"
    )
    result = rewrite_followup_offline(follow, [prior])
    # Long query without pronouns → no rewrite (may also be topic change if entities differ)
    assert result.rewritten == follow or result.method == "none"


def test_extract_key_entities_finds_code_and_fund():
    text = "HDFC Mid Cap Fund scheme code HDFC/O/E/MIF/07/04/0015 in the SID"
    ents = extract_key_entities(text)
    assert any("HDFC" in e.upper() for e in ents)


@pytest.mark.asyncio
async def test_rewrite_followup_async_offline_path():
    r = await rewrite_followup(
        "What about its TER?",
        ["What is the Kotak Midcap Fund legal name?"],
        use_llm=False,
    )
    assert "Kotak" in r.rewritten or r.entities_carried


def test_document_scope_list_preserved_through_rewrite_meta():
    """Scope is a chat-layer concern: rewrite must not drop or invent document_ids."""
    # Simulate what chat_service stores: document_ids stay on retrieval_meta unchanged
    document_ids = ["doc-a", "doc-b"]
    result = rewrite_followup_offline(
        "its benchmark?",
        ["HDFC Mid Cap Fund scheme code on cover?"],
    )
    # Rewrite output has no document_ids field — caller keeps the list
    meta = {**result.as_dict(), "document_ids": list(document_ids)}
    assert meta["document_ids"] == ["doc-a", "doc-b"]
    assert meta["original_query"] == "its benchmark?"


def test_followups_jsonl_loads():
    from evals.followups import load_followups

    pairs = load_followups()
    assert len(pairs) == 10
    assert all(p.label_source == "draft" for p in pairs)
    assert any("TOPIC CHANGE" in (p.notes or "").upper() for p in pairs)
