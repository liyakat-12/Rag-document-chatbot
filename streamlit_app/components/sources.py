"""Sources and advanced retrieval details under assistant answers."""

from __future__ import annotations

from typing import Any

import streamlit as st

import components._pathfix  # noqa: F401
from components import confidence_bar
from components.citation_viewer import open_citation_viewer


def render_sources(sources: list[dict[str, Any]] | None, *, msg_index: int = 0) -> None:
    sources = sources or []
    if not sources:
        return
    with st.expander(f"Supporting evidence · {len(sources)} source(s)", expanded=True):
        for i, s in enumerate(sources):
            fname = s.get("filename") or "document.pdf"
            page = s.get("page_number", "?")
            loc_type = s.get("location_type") or "page"
            location = s.get("location") or f"page {page}"
            score = float(s.get("score") or 0) * 100
            content = s.get("content") or ""
            excerpt = content[:420]
            if loc_type == "section":
                st.markdown(f"**{fname}** · {location}")
            else:
                st.markdown(f"**{fname}** · page {page}")
            st.caption(
                f"Fused retrieval rank strength {score:.0f}% "
                "(ranking signal, not verified accuracy)"
            )
            # Source preview — sentence-select context uses >>>highlight<<< markers
            if s.get("context_preview") or ">>>" in content:
                st.caption("Context (selected sentences highlighted)")
                st.code(content[:1200] + ("…" if len(content) > 1200 else ""), language=None)
            elif s.get("selected_sentence"):
                st.markdown(f"> {content}")
            else:
                preview = excerpt + ("…" if len(content) > 420 else "")
                st.write(preview)
            doc_id = s.get("document_id") or ""
            if doc_id and st.button(
                "Open in viewer",
                key=f"view_cite_{msg_index}_{i}",
                use_container_width=True,
            ):
                open_citation_viewer(
                    document_id=doc_id,
                    filename=fname,
                    page_number=int(page) if str(page).isdigit() else 1,
                    span=content[:800],
                    chunk_text=content,
                )
                st.rerun()
            if i < len(sources) - 1:
                st.divider()


def render_confidence(confidence: float | None) -> None:
    # Hide for greetings / not-found (0.0)
    if confidence is None or confidence <= 0:
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
    if retrieval.get("strategy") in {"greeting", "empty_library"}:
        return
    with st.expander("Advanced retrieval details", expanded=False):
        st.caption("Hybrid search diagnostics (FAISS + BM25 → RRF).")
        orig_q = retrieval.get("original_query")
        rewr_q = retrieval.get("rewritten_query") or retrieval.get("retrieval_query")
        follow = retrieval.get("followup") or {}
        if orig_q or rewr_q or follow:
            st.markdown("**Query rewrite**")
            if orig_q:
                st.caption(f"Original: {orig_q}")
            if rewr_q and rewr_q != orig_q:
                st.caption(f"Rewritten: {rewr_q}")
            if follow.get("rewrite_method"):
                st.caption(
                    f"Method: {follow.get('rewrite_method')}"
                    + (
                        f" · carried: {', '.join(follow.get('entities_carried') or [])}"
                        if follow.get("entities_carried")
                        else ""
                    )
                )
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
