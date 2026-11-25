"""Obvious out-of-scope questions must return the not-found message."""

from __future__ import annotations

import asyncio

import pytest
from langchain_core.documents import Document as LCDocument

from backend.app.rag.qa_chain import NOT_FOUND_MESSAGE, generate_answer


@pytest.mark.asyncio
async def test_capital_of_france_not_found_on_sample_chunk(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "extractive")
    monkeypatch.setenv("ANSWER_SENTENCE_SELECT", "true")
    monkeypatch.setenv("ANSWER_SENTENCE_SELECT_MODE", "clean_chunk")
    monkeypatch.setenv("ANSWER_REFUSE_ZERO_OVERLAP", "true")
    from backend.app.config import get_settings

    get_settings.cache_clear()

    docs = [
        (
            LCDocument(
                page_content=(
                    "HDFC Mid Cap Fund invests predominantly in mid-cap stocks. "
                    "The scheme code appears on the cover page of the SID."
                ),
                metadata={
                    "filename": "sid_hdfc_midcap.pdf",
                    "page_number": 1,
                    "chunk_id": "c1",
                    "document_id": "d1",
                },
            ),
            0.4,
        )
    ]
    answer, _ = await generate_answer("What is the capital of France?", docs)
    assert NOT_FOUND_MESSAGE in answer or "couldn't find" in answer.lower()


@pytest.mark.asyncio
async def test_unrelated_celebrity_not_found(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "extractive")
    monkeypatch.setenv("ANSWER_SENTENCE_SELECT", "false")
    monkeypatch.setenv("ANSWER_REFUSE_ZERO_OVERLAP", "true")
    from backend.app.config import get_settings

    get_settings.cache_clear()

    docs = [
        (
            LCDocument(
                page_content="Leave entitlement is 20 days per calendar year for full-time staff.",
                metadata={
                    "filename": "policy_leave_entitlement.pdf",
                    "page_number": 1,
                    "chunk_id": "c2",
                    "document_id": "d2",
                },
            ),
            0.3,
        )
    ]
    answer, _ = await generate_answer(
        "Who won the FIFA World Cup in 2018?",
        docs,
    )
    assert "couldn't find" in answer.lower()
