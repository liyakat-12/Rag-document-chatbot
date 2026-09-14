"""Analytics dashboard using existing admin stats."""

from __future__ import annotations

from typing import Callable

import streamlit as st

import components._pathfix  # noqa: F401
from components import friendly_error


def render_analytics(client_factory: Callable) -> None:
    st.markdown("## Analytics")
    st.caption("Operational metrics from your local DocuMind deployment.")

    if st.button("Refresh"):
        st.rerun()

    try:
        stats = client_factory().admin_stats()
        health = client_factory().health()
    except Exception as exc:
        st.error(friendly_error(exc))
        return

    docs = stats.get("documents") or {}
    hits = int(stats.get("cache_hits") or 0)
    misses = int(stats.get("cache_misses") or 0)
    total_cache = hits + misses
    hit_rate = f"{(hits / total_cache * 100):.0f}%" if total_cache else "—"

    m = st.columns(4)
    m[0].metric("Documents indexed", docs.get("indexed_documents", 0))
    m[1].metric("Conversations", stats.get("total_sessions", 0))
    m[2].metric("Answers", stats.get("questions_answered", 0))
    m[3].metric("Cache hit rate", hit_rate)

    m2 = st.columns(4)
    m2[0].metric("Pages processed", docs.get("total_pages", 0))
    m2[1].metric("Chunks", docs.get("total_chunks", 0))
    m2[2].metric("Feedback ↑", stats.get("feedback_up", 0))
    m2[3].metric("Feedback ↓", stats.get("feedback_down", 0))

    m3 = st.columns(3)
    m3[0].metric("Messages", stats.get("total_messages", 0))
    m3[1].metric("Tokens used", stats.get("total_tokens_used", 0))
    m3[2].metric("Storage (bytes)", docs.get("total_size_bytes", 0))

    st.divider()
    st.success(
        f"API healthy · {health.get('app')} · "
        f"LLM `{health.get('llm_provider')}` · "
        f"embeddings `{health.get('embedding_provider', '—')}` · "
        f"retrieval `{health.get('retrieval_strategy', 'hybrid_rrf')}`"
    )
    st.caption(
        "Average retrieval/response latency appears per answer under Retrieval details. "
        "Global averages are not stored in the current database schema."
    )
