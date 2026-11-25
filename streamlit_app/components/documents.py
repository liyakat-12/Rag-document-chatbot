"""Documents management page."""

from __future__ import annotations

from html import escape
from typing import Any, Callable

import streamlit as st

import components._pathfix  # noqa: F401
from components import STAGE_LABELS, fmt_bytes, fmt_status, friendly_error
from components.citation_viewer import render_doc_browser


def _show_stages(stages: list[dict[str, Any]]) -> None:
    if not stages:
        return
    st.markdown("**Indexing progress**")
    st.caption("Stages reported by the backend for this upload (not a simulated percentage).")
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
    if stages and stages[-1].get("name") == "failed":
        st.error("Indexing failed. Check the file is a text-extractable PDF and try again.")
    elif stages and all(s.get("ok") for s in stages):
        st.success("Document indexed and available in search.")


def render_documents(client_factory: Callable, max_mb: int = 40) -> None:
    st.markdown('<p class="page-kicker">Library</p>', unsafe_allow_html=True)
    st.markdown("## Documents")
    st.caption(f"PDF only · up to {max_mb} MB each · indexed locally with hybrid search")

    if not st.session_state.get("backend_ok"):
        st.warning(
            "Backend unavailable — upload and indexing require the API. "
            "Start the backend, then use **Retry connection** in the sidebar."
        )
        return

    uploads = st.file_uploader(
        "Upload PDF",
        type=["pdf"],
        accept_multiple_files=True,
        help=f"Drag and drop PDFs (max {max_mb} MB each). Only text-extractable PDFs can be indexed.",
    )
    if uploads:
        st.caption(f"{len(uploads)} file(s) selected · ready to upload")
    if uploads and st.button("Upload & index", type="primary"):
        too_big = [f.name for f in uploads if f.size > max_mb * 1024 * 1024]
        if too_big:
            st.error(f"These files exceed {max_mb} MB: {', '.join(too_big)}")
        else:
            # Synchronous ingest — show truthful spinner + backend stage list after return
            with st.spinner(
                "Uploading → extracting text → chunking → embeddings → updating FAISS & BM25…"
            ):
                try:
                    payload = [(f.name, f.getvalue(), "application/pdf") for f in uploads]
                    result = client_factory().upload(payload)
                    st.session_state.last_ingest_stages = result.get("stages") or []
                    st.session_state.pop("_indexed_docs_cache", None)
                    st.session_state.pop("_indexed_docs_cache_at", None)
                    st.session_state["_force_health_refresh"] = True
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
            with st.spinner("Re-indexing all documents…"):
                try:
                    res = client_factory().reindex()
                    st.session_state.pop("_indexed_docs_cache", None)
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
        st.markdown(
            """
            <div class="hero-wrap" style="text-align:left;padding:1.25rem;">
              <p class="hero-title" style="text-align:left;font-size:1.35rem;">No documents yet</p>
              <p class="hero-sub" style="text-align:left;margin:0;">
                Upload a PDF above to extract text, create chunks, and build the hybrid index.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    for d in docs:
        name = escape(d.get("original_filename") or "document.pdf")
        label, css = fmt_status(d.get("status", ""))
        pages = d.get("page_count", 0)
        size = fmt_bytes(int(d.get("file_size") or 0))
        chunks = d.get("chunk_count", 0)
        err = d.get("error_message")
        confirm_key = f"confirm_del_{d['id']}"
        st.markdown(
            f"""
            <div class="doc-card">
              <div class="doc-card-title" title="{name}">{name}</div>
              <div class="doc-card-meta">{pages} pages · {chunks} chunks · {size}</div>
              <span class="{css}">{label}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if err and (d.get("status") or "").lower() == "error":
            st.caption(f"Error: {err[:200]}")
        with st.expander("Metadata & page preview", expanded=False):
            render_doc_browser(client_factory, d)
        if st.session_state.get(confirm_key):
            st.warning(f"Delete **{d.get('original_filename')}** permanently?")
            c_yes, c_no = st.columns([1, 1])
            with c_yes:
                if st.button(
                    "Confirm delete",
                    key=f"yes_{d['id']}",
                    type="primary",
                    use_container_width=True,
                ):
                    try:
                        client_factory().delete_document(d["id"])
                        st.session_state.pop(confirm_key, None)
                        st.session_state.pop("_indexed_docs_cache", None)
                        sel = st.session_state.get("selected_document_ids") or []
                        st.session_state.selected_document_ids = [
                            x for x in sel if x != d["id"]
                        ]
                        st.rerun()
                    except Exception as exc:
                        st.error(friendly_error(exc))
            with c_no:
                if st.button("Cancel", key=f"no_{d['id']}", use_container_width=True):
                    st.session_state.pop(confirm_key, None)
                    st.rerun()
        elif st.button("Delete", key=f"del_doc_{d['id']}", use_container_width=True):
            st.session_state[confirm_key] = True
            st.rerun()
