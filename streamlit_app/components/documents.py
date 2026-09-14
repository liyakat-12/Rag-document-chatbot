"""Documents management page."""

from __future__ import annotations

from html import escape
from typing import Any, Callable

import streamlit as st

import components._pathfix  # noqa: F401
from components import STAGE_LABELS, fmt_bytes, fmt_status, friendly_error


def _show_stages(stages: list[dict[str, Any]]) -> None:
    if not stages:
        return
    st.markdown("**Processing**")
    for stage in stages:
        name = STAGE_LABELS.get(stage.get("name", ""), stage.get("name", ""))
        ok = stage.get("ok", False)
        mark = "✓" if ok else "!"
        detail = stage.get("detail") or ""
        extra = f" · {detail}" if detail else ""
        css = "stage-ok" if ok else "status-err"
        st.markdown(
            f'<p class="stage-line"><span class="{css}">{mark}</span> {name}{extra}</p>',
            unsafe_allow_html=True,
        )
    if stages and stages[-1].get("name") != "failed" and all(s.get("ok") for s in stages):
        st.success("✓ Document ready")


def render_documents(client_factory: Callable, max_mb: int = 40) -> None:
    st.markdown("## Documents")
    st.caption(f"Upload PDFs · max {max_mb} MB per file")

    uploads = st.file_uploader(
        "Upload PDF",
        type=["pdf"],
        accept_multiple_files=True,
        help=f"Drag and drop PDFs (max {max_mb} MB each)",
    )
    if uploads and st.button("Upload & index", type="primary"):
        too_big = [f.name for f in uploads if f.size > max_mb * 1024 * 1024]
        if too_big:
            st.error(f"These files exceed {max_mb} MB: {', '.join(too_big)}")
        else:
            with st.spinner("Indexing documents…"):
                try:
                    payload = [(f.name, f.getvalue(), "application/pdf") for f in uploads]
                    result = client_factory().upload(payload)
                    st.session_state.last_ingest_stages = result.get("stages") or []
                    st.rerun()
                except Exception as exc:
                    st.error(friendly_error(exc))

    stages = st.session_state.get("last_ingest_stages")
    if stages:
        _show_stages(stages)
        if st.button("Dismiss"):
            st.session_state.last_ingest_stages = None
            st.rerun()

    st.divider()
    c1, c2 = st.columns([3, 1])
    with c1:
        st.markdown("### Library")
    with c2:
        if st.button("Re-index all", use_container_width=True):
            with st.spinner("Re-indexing…"):
                try:
                    res = client_factory().reindex()
                    st.success(
                        f"Reindexed {res.get('documents_reindexed')} docs / "
                        f"{res.get('chunks_indexed')} chunks"
                    )
                except Exception as exc:
                    st.error(friendly_error(exc))

    try:
        docs = client_factory().list_documents()
    except Exception as exc:
        st.error(friendly_error(exc))
        return

    if not docs:
        st.info("No documents yet. Upload a PDF to get started.")
        return

    for d in docs:
        name = escape(d.get("original_filename") or "document.pdf")
        label, css = fmt_status(d.get("status", ""))
        pages = d.get("page_count", 0)
        size = fmt_bytes(int(d.get("file_size") or 0))
        st.markdown(
            f"""
            <div class="doc-card">
              <div style="font-size:1.05rem;font-weight:650;margin-bottom:.35rem;">{name}</div>
              <div style="color:var(--dm-muted);font-size:.9rem;margin-bottom:.35rem;">
                {pages} pages · {size}
              </div>
              <span class="{css}">✓ {label}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        b1, b2 = st.columns(2)
        with b1:
            st.caption("Re-index via “Re-index all” above")
        with b2:
            if st.button("Delete", key=f"del_doc_{d['id']}"):
                try:
                    client_factory().delete_document(d["id"])
                    st.rerun()
                except Exception as exc:
                    st.error(friendly_error(exc))
