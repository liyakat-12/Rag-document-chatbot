"""In-app PDF citation viewer with span highlighting."""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

import components._pathfix  # noqa: F401
from components import friendly_error


def _highlight_span_in_text(chunk_text: str, span: str) -> str:
    text = chunk_text or ""
    needle = (span or "").strip()
    if not needle:
        return text
    idx = text.lower().find(needle.lower())
    if idx >= 0:
        end = idx + len(needle)
        return text[:idx] + ">>>" + text[idx:end] + "<<<" + text[end:]
    return text


def open_citation_viewer(
    *,
    document_id: str,
    filename: str,
    page_number: int,
    span: str = "",
    chunk_text: str = "",
) -> None:
    st.session_state["citation_viewer"] = {
        "document_id": document_id,
        "filename": filename,
        "page_number": int(page_number or 1),
        "span": span or "",
        "chunk_text": chunk_text or "",
    }


def clear_citation_viewer() -> None:
    st.session_state.pop("citation_viewer", None)


def render_citation_viewer_panel(client_factory: Callable) -> None:
    """Side panel: rendered page + nav + fallback chunk highlight."""
    state = st.session_state.get("citation_viewer")
    if not state:
        return

    doc_id = state.get("document_id") or ""
    page = int(state.get("page_number") or 1)
    span = state.get("span") or ""
    chunk_text = state.get("chunk_text") or ""
    filename = state.get("filename") or "document.pdf"

    st.markdown("---")
    st.markdown("### Source viewer")
    top = st.columns([4, 1])
    with top[0]:
        st.caption(f"{filename} · page {page}")
    with top[1]:
        if st.button("Close viewer", key="close_cite_viewer", use_container_width=True):
            clear_citation_viewer()
            st.rerun()

    page_count = None
    match_mode = ""
    try:
        png, headers = client_factory().document_page_image(doc_id, page, span=span)
        match_mode = headers.get("match_mode") or ""
        page_count = int(headers.get("page_count") or 0) or None
        st.image(png, use_container_width=True)
        if match_mode:
            st.caption(f"Highlight match: `{match_mode}`")
        if match_mode == "chunk_fallback" or headers.get("chunk_fallback") == "1":
            marked = _highlight_span_in_text(chunk_text or span, span)
            st.info("Could not locate the span on the page image — showing chunk text.")
            st.code(marked, language=None)
    except Exception as exc:
        st.warning(friendly_error(exc))
        if chunk_text or span:
            st.code(_highlight_span_in_text(chunk_text or span, span), language=None)

    nav = st.columns([1, 1, 2])
    max_page = page_count or page
    with nav[0]:
        if st.button("← Prev", key="cite_prev", disabled=page <= 1, use_container_width=True):
            st.session_state["citation_viewer"]["page_number"] = max(1, page - 1)
            # Keep span only when staying on the cited page intent; clear when browsing
            st.session_state["citation_viewer"]["span"] = ""
            st.rerun()
    with nav[1]:
        if st.button(
            "Next →",
            key="cite_next",
            disabled=page_count is not None and page >= max_page,
            use_container_width=True,
        ):
            st.session_state["citation_viewer"]["page_number"] = page + 1
            st.session_state["citation_viewer"]["span"] = ""
            st.rerun()
    with nav[2]:
        if page_count:
            st.caption(f"Page {page} of {page_count}")


def render_doc_browser(client_factory: Callable, doc: dict[str, Any]) -> None:
    """Documents-page page navigator with metadata and processing status."""
    doc_id = doc.get("id") or ""
    name = doc.get("original_filename") or "document.pdf"
    pages = int(doc.get("page_count") or 0)
    key = f"browse_page_{doc_id}"
    if key not in st.session_state:
        st.session_state[key] = 1

    st.markdown("**Document metadata**")
    st.caption(
        f"Status: {doc.get('status')} · {pages} pages · "
        f"{doc.get('chunk_count', 0)} chunks · "
        f"updated {doc.get('updated_at') or '—'}"
    )
    if doc.get("error_message"):
        st.caption(f"Processing note: {doc.get('error_message')[:240]}")

    # Optional low-text pages from meta endpoint
    try:
        meta = client_factory().document_meta(doc_id)
        low = meta.get("low_text_pages") or []
        if low:
            st.warning(
                "Low-text pages flagged: "
                + ", ".join(f"p{p.get('page')} ({p.get('chars')}c)" for p in low[:12])
                + ("…" if len(low) > 12 else "")
            )
    except Exception:
        meta = None

    if pages < 1:
        return

    c1, c2, c3 = st.columns([1, 2, 1])
    with c1:
        if st.button("←", key=f"doc_prev_{doc_id}", disabled=st.session_state[key] <= 1):
            st.session_state[key] = max(1, st.session_state[key] - 1)
            st.rerun()
    with c2:
        st.caption(f"Preview page {st.session_state[key]} / {pages}")
    with c3:
        if st.button("→", key=f"doc_next_{doc_id}", disabled=st.session_state[key] >= pages):
            st.session_state[key] = min(pages, st.session_state[key] + 1)
            st.rerun()

    try:
        png, headers = client_factory().document_page_image(
            doc_id, int(st.session_state[key]), span=""
        )
        st.image(png, use_container_width=True)
        if headers.get("cache_hit") == "1":
            st.caption("Cached page render")
    except Exception as exc:
        st.caption(f"Preview unavailable: {friendly_error(exc)}")
