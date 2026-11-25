"""Sources and advanced retrieval details under assistant answers."""

from __future__ import annotations

from typing import Any

import streamlit as st

import components._pathfix  # noqa: F401
from components import confidence_badge, confidence_bar
from components.citation_viewer import open_citation_viewer


def _developer_mode() -> bool:
    try:
        from backend.app.config import get_settings

        return bool(getattr(get_settings(), "ui_developer_mode", False))
    except Exception:
        return bool(st.session_state.get("ui_developer_mode", False))


def _one_line_preview(content: str, limit: int = 120) -> str:
    from components import truncate_at_word

    text = (content or "").replace(">>>", "").replace("<<<", "")
    text = " ".join(text.split())
    return truncate_at_word(text, limit)


def _unique_doc_count(sources: list[dict[str, Any]]) -> int:
    names = {
        (s.get("filename") or s.get("document_id") or "").strip().lower()
        for s in sources
        if (s.get("filename") or s.get("document_id"))
    }
    return len(names) or (1 if sources else 0)


def render_sources(sources: list[dict[str, Any]] | None, *, msg_index: int = 0) -> None:
    sources = sources or []
    if not sources:
        return
    dev = _developer_mode()
    with st.expander(f"Sources · {len(sources)}", expanded=False):
        for i, s in enumerate(sources):
            fname = s.get("filename") or "document.pdf"
            page = s.get("page_number", "?")
            loc_type = s.get("location_type") or "page"
            location = s.get("location") or f"page {page}"
            content = s.get("content") or ""
            preview = _one_line_preview(content)
            if loc_type == "section":
                st.markdown(f"**{fname}** · {location}")
            else:
                st.markdown(f"**{fname}** · page {page}")
            st.caption(preview)

            # Full text on click — context_preview collapsed (answer not repeated verbatim)
            label = (
                "Show highlighted context"
                if s.get("context_preview") or ">>>" in content
                else "Show full excerpt"
            )
            with st.expander(label, expanded=False):
                if s.get("context_preview") or ">>>" in content:
                    st.caption("Selected sentences marked with >>> <<<")
                    st.code(
                        content[:2000] + ("…" if len(content) > 2000 else ""),
                        language=None,
                    )
                else:
                    st.write(content)

            if dev:
                score = float(s.get("score") or 0) * 100
                st.caption(
                    f"Fused retrieval rank strength {score:.0f}% "
                    "(ranking signal, not verified accuracy)"
                )

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


def render_confidence(
    confidence: float | None,
    *,
    sources: list[dict[str, Any]] | None = None,
) -> None:
    if confidence is None or confidence <= 0:
        return
    n_docs = _unique_doc_count(sources or [])
    st.markdown(confidence_badge(n_docs), unsafe_allow_html=True)
    if _developer_mode():
        st.markdown(confidence_bar(confidence), unsafe_allow_html=True)


def render_retrieval_details(
    retrieval: dict[str, Any] | None,
    timings: dict[str, Any] | None = None,
    *,
    sources: list[dict[str, Any]] | None = None,
) -> None:
    """Technical diagnostics — collapsed; ranking scores only in developer mode."""
    retrieval = retrieval or {}
    timings = timings or {}
    if not retrieval and not timings:
        return
    if retrieval.get("strategy") in {"greeting", "empty_library"}:
        return
    with st.expander("Advanced retrieval details", expanded=False):
        st.caption(
            "Query rewriting (optional) → hybrid search (FAISS + BM25 → RRF) "
            "→ cross-encoder reranking (optional)."
        )
        rewrite = retrieval.get("query_rewriting") or {}
        reranker = retrieval.get("reranker") or {}
        if rewrite or retrieval.get("candidate_count") is not None or reranker.get("enabled"):
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
            if reranker.get("enabled"):
                if reranker.get("fallback"):
                    st.caption(f"Cross-encoder: fallback to RRF ({reranker.get('fallback')})")
                else:
                    st.caption(
                        f"Cross-encoder: {reranker.get('model', 'enabled')} · "
                        f"{reranker.get('latency_ms', '—')} ms"
                    )
            else:
                st.caption("Cross-encoder: disabled")
        if not _developer_mode():
            st.caption("Enable UI_DEVELOPER_MODE to see ranking scores and percentages.")
            cols = st.columns(3)
            cols[0].metric("Strategy", str(retrieval.get("strategy") or "hybrid_rrf"))
            cols[1].metric("Top-K", retrieval.get("top_k", "—"))
            cols[2].metric(
                "Retrieve ms",
                timings.get("retrieval_ms") or retrieval.get("latency_ms") or "—",
            )
            return

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

        if sources:
            st.markdown("**Source ranking signals**")
            for h in sources:
                sc = float(h.get("score") or 0)
                st.write(
                    f"{h.get('filename')} p.{h.get('page_number')} · score {sc:.4f} "
                    f"({sc * 100:.0f}%)"
                )

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
