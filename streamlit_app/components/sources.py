"""Sources and advanced retrieval details under assistant answers."""

from __future__ import annotations

from typing import Any

import streamlit as st

import components._pathfix  # noqa: F401
from components import confidence_bar


def render_sources(sources: list[dict[str, Any]] | None) -> None:
    sources = sources or []
    if not sources:
        st.caption("No sources for this answer.")
        return
    st.markdown(f"**Sources · {len(sources)}**")
    for i, s in enumerate(sources):
        fname = s.get("filename") or "document.pdf"
        page = s.get("page_number", "?")
        score = float(s.get("score") or 0) * 100
        excerpt = (s.get("content") or "")[:420]
        with st.expander(
            f"{fname} · p.{page} · {score:.0f}%",
            expanded=(i == 0 and len(sources) <= 2),
        ):
            st.caption(f"Relevance (fused) {score:.0f}%")
            st.write(excerpt + ("…" if len(s.get("content") or "") > 420 else ""))


def render_confidence(confidence: float | None) -> None:
    if confidence is None:
        return
    st.markdown(confidence_bar(confidence), unsafe_allow_html=True)


def render_retrieval_details(
    retrieval: dict[str, Any] | None,
    timings: dict[str, Any] | None = None,
) -> None:
    """Technical diagnostics — collapsed by default."""
    retrieval = retrieval or {}
    timings = timings or {}
    if not retrieval and not timings:
        return
    with st.expander("Advanced Retrieval Details", expanded=False):
        st.caption(
            "Query rewriting (optional) → hybrid retrieval (FAISS + BM25 → RRF) "
            "→ cross-encoder reranking (optional)."
        )
        rewrite = retrieval.get("query_rewriting") or {}
        reranker = retrieval.get("reranking") or {}
        if rewrite or retrieval.get("candidate_count") is not None or reranker:
            st.markdown("**Query rewriting and reranking**")
            if rewrite:
                st.caption(
                    f"Rewrite: {rewrite.get('method', 'unknown')} · "
                    f"{rewrite.get('variants', len(retrieval.get('query_variants') or []))} "
                    "query variant(s)"
                )
                for index, query in enumerate(retrieval.get("query_variants") or [], start=1):
                    st.write(f"{index}. {query}")
            if retrieval.get("candidate_count") is not None:
                st.caption(
                    f"Candidate pool: {retrieval.get('candidate_count')} chunks "
                    f"before final top-{retrieval.get('top_k', 'K')} selection"
                )
            if reranker:
                if reranker.get("method") == "rrf_fallback":
                    st.caption("Cross-encoder unavailable; using fused RRF ranking.")
                elif reranker.get("method") == "cross_encoder":
                    st.caption(
                        f"Cross-encoder: {reranker.get('model', 'enabled')} · "
                        f"{reranker.get('latency_ms', '—')} ms"
                    )
                else:
                    st.caption("Cross-encoder disabled")
        cols = st.columns(3)
        cols[0].metric("Strategy", str(retrieval.get("strategy") or "hybrid_rrf"))
        cols[1].metric("Top-K", retrieval.get("top_k", "—"))
        cols[2].metric(
            "Retrieve ms",
            timings.get("retrieval_ms") or retrieval.get("latency_ms") or "—",
        )
        if timings.get("generation_ms") is not None:
            st.caption(
                f"Generation {timings.get('generation_ms')} ms · "
                f"Total {timings.get('total_ms', '—')} ms"
            )
        dense_w = retrieval.get("dense_weight")
        sparse_w = retrieval.get("sparse_weight")
        if dense_w is not None:
            st.caption(f"Dense weight {dense_w} · Sparse weight {sparse_w}")

        sem = retrieval.get("semantic") or {}
        bm = retrieval.get("bm25") or {}
        fused = retrieval.get("fused") or {}
        c1, c2, c3 = st.columns(3)
        with c1:
            st.markdown("**Semantic (FAISS)**")
            st.caption(f"{sem.get('count', 0)} hits · {sem.get('latency_ms', '—')} ms")
            for h in sem.get("hits") or []:
                st.write(
                    f"#{h.get('rank')} {h.get('filename')} p.{h.get('page_number')} "
                    f"({h.get('score')})"
                )
        with c2:
            st.markdown("**BM25**")
            st.caption(f"{bm.get('count', 0)} hits · {bm.get('latency_ms', '—')} ms")
            for h in bm.get("hits") or []:
                st.write(
                    f"#{h.get('rank')} {h.get('filename')} p.{h.get('page_number')} "
                    f"({h.get('score')})"
                )
        with c3:
            st.markdown("**Fused (RRF)**")
            st.caption(f"{fused.get('count', 0)} results")
            for h in fused.get("hits") or []:
                st.write(
                    f"#{h.get('rank')} {h.get('filename')} p.{h.get('page_number')} "
                    f"({h.get('score')})"
                )
