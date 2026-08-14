"""
DocuMind RAG — Streamlit frontend
Run: streamlit run streamlit_app/app.py
Requires the FastAPI backend on http://localhost:8000
"""

from __future__ import annotations

import os
from typing import Any

import streamlit as st

from api_client import RagClient
from backend_runtime import start_backend


@st.cache_resource(show_spinner="Starting backend service…")
def _bootstrap_backend() -> bool:
    """Ensure the FastAPI backend is reachable, starting it in-process if
    nothing is already listening (e.g. on Streamlit Community Cloud, where
    only this single service gets deployed)."""
    start_backend()
    return True


_bootstrap_backend()

API_BASE = os.getenv("VITE_API_BASE_URL") or os.getenv("API_BASE_URL") or "http://localhost:8000/api/v1"
MAX_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "40"))

st.set_page_config(
    page_title="DocuMind RAG",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
  .block-container { padding-top: 1.2rem; padding-bottom: 2rem; max-width: 1200px; }
  .source-box {
    border: 1px solid rgba(13,110,90,.25);
    border-radius: 10px;
    padding: .75rem .9rem;
    margin-bottom: .55rem;
    background: rgba(13,110,90,.06);
    font-size: .9rem;
  }
  .meta-chip {
    display: inline-block;
    padding: .15rem .55rem;
    border-radius: 999px;
    background: rgba(13,110,90,.14);
    color: #0d6e5a;
    font-weight: 600;
    font-size: .75rem;
    margin-right: .35rem;
  }
  div[data-testid="stChatMessage"] { margin-bottom: .35rem; }
</style>
""",
    unsafe_allow_html=True,
)


def client() -> RagClient:
    return RagClient(base_url=API_BASE)


def init_state() -> None:
    defaults: dict[str, Any] = {
        "session_id": None,
        "messages": [],  # {role, content, id?, confidence?, sources?, rating?}
        "last_sources": [],
        "dark_mode": False,
        "page": "Chat",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def apply_theme() -> None:
    if st.session_state.dark_mode:
        st.markdown(
            """
            <style>
              .stApp {
                background: radial-gradient(900px 500px at 0% 0%, #1a2e28, #121410 55%);
                color: #ece8df;
              }
              [data-testid="stSidebar"] {
                background: #161912 !important;
              }
              .source-box { background: rgba(61,186,154,.1); border-color: #2f352a; }
              .meta-chip { background: rgba(61,186,154,.18); color: #3dba9a; }
            </style>
            """,
            unsafe_allow_html=True,
        )


def new_chat() -> None:
    st.session_state.session_id = None
    st.session_state.messages = []
    st.session_state.last_sources = []


def load_session(session_id: str) -> None:
    data = client().get_session(session_id)
    st.session_state.session_id = session_id
    st.session_state.messages = [
        {
            "id": m.get("id"),
            "role": m["role"],
            "content": m["content"],
            "confidence": m.get("confidence"),
            "sources": m.get("sources") or [],
            "rating": m.get("rating", "none"),
        }
        for m in data.get("messages", [])
    ]
    for m in reversed(st.session_state.messages):
        if m["role"] == "assistant" and m.get("sources"):
            st.session_state.last_sources = m["sources"]
            break


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("### DocuMind RAG")
        st.caption("PDF Q&A with citations")

        st.session_state.page = st.radio(
            "Navigate",
            ["Chat", "Admin"],
            horizontal=True,
            label_visibility="collapsed",
        )

        st.session_state.dark_mode = st.toggle("Dark mode", value=st.session_state.dark_mode)

        st.divider()
        st.markdown("#### Chat history")
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("New chat", use_container_width=True):
                new_chat()
                st.rerun()
        with col_b:
            if st.button("Refresh", use_container_width=True):
                st.rerun()

        try:
            sessions = client().list_sessions()
        except Exception as exc:
            st.warning(f"Backend offline: {exc}")
            sessions = []

        for s in sessions:
            c1, c2 = st.columns([4, 1])
            with c1:
                label = f"{s['title'][:36]}"
                if st.button(label, key=f"sess_{s['id']}", use_container_width=True):
                    load_session(s["id"])
                    st.rerun()
            with c2:
                if st.button("🗑", key=f"del_sess_{s['id']}"):
                    client().delete_session(s["id"])
                    if st.session_state.session_id == s["id"]:
                        new_chat()
                    st.rerun()

        st.divider()
        st.markdown("#### Documents")
        st.caption(f"Max upload size: **{MAX_MB} MB** per file · PDF only")

        uploads = st.file_uploader(
            "Upload PDFs",
            type=["pdf"],
            accept_multiple_files=True,
            help=f"Drag and drop PDFs here (max {MAX_MB} MB each)",
        )
        if uploads and st.button("Index uploaded PDFs", type="primary", use_container_width=True):
            too_big = [f.name for f in uploads if f.size > MAX_MB * 1024 * 1024]
            if too_big:
                st.error(f"These files exceed {MAX_MB} MB: {', '.join(too_big)}")
            else:
                with st.spinner("Uploading & indexing…"):
                    try:
                        payload = [
                            (f.name, f.getvalue(), "application/pdf") for f in uploads
                        ]
                        result = client().upload(payload)
                        st.success(result.get("message", "Uploaded"))
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))

        try:
            docs = client().list_documents()
        except Exception:
            docs = []

        for d in docs:
            with st.expander(d.get("original_filename", d["id"])[:40]):
                st.write(
                    f"Pages: {d.get('page_count', 0)} · Chunks: {d.get('chunk_count', 0)} · "
                    f"Status: `{d.get('status')}` · "
                    f"Size: {d.get('file_size', 0) / (1024 * 1024):.1f} MB"
                )
                if st.button("Delete document", key=f"del_doc_{d['id']}"):
                    client().delete_document(d["id"])
                    st.rerun()

        if st.button("Re-index all documents", use_container_width=True):
            with st.spinner("Re-indexing…"):
                try:
                    res = client().reindex()
                    st.success(
                        f"Reindexed {res.get('documents_reindexed')} docs / "
                        f"{res.get('chunks_indexed')} chunks"
                    )
                except Exception as exc:
                    st.error(str(exc))


# ---------------------------------------------------------------------------
# Chat page
# ---------------------------------------------------------------------------
def render_chat() -> None:
    left, right = st.columns([2.2, 1])

    with left:
        st.markdown("## Ask your documents")
        if not st.session_state.messages:
            st.info("Upload PDFs in the sidebar, then ask a question below.")

        for i, msg in enumerate(st.session_state.messages):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg["role"] == "assistant":
                    meta_parts = []
                    if isinstance(msg.get("confidence"), (int, float)):
                        meta_parts.append(
                            f'<span class="meta-chip">Confidence {(msg["confidence"] * 100):.0f}%</span>'
                        )
                    if msg.get("cached"):
                        meta_parts.append('<span class="meta-chip">cached</span>')
                    if meta_parts:
                        st.markdown("".join(meta_parts), unsafe_allow_html=True)

                    b1, b2, b3, b4 = st.columns(4)
                    with b1:
                        if st.button("Copy", key=f"copy_{i}"):
                            st.session_state[f"_copied_{i}"] = msg["content"]
                            st.toast("Answer ready — select text or use export PDF")
                    with b2:
                        if st.button("👍", key=f"up_{i}") and msg.get("id"):
                            try:
                                client().rate_message(msg["id"], "up")
                                st.session_state.messages[i]["rating"] = "up"
                                st.toast("Thanks for the feedback")
                            except Exception as exc:
                                st.error(str(exc))
                    with b3:
                        if st.button("👎", key=f"down_{i}") and msg.get("id"):
                            try:
                                client().rate_message(msg["id"], "down")
                                st.session_state.messages[i]["rating"] = "down"
                                st.toast("Thanks for the feedback")
                            except Exception as exc:
                                st.error(str(exc))
                    with b4:
                        rating = msg.get("rating")
                        if rating and rating != "none":
                            st.caption(f"Rated: {rating}")

        prompt = st.chat_input("Ask a question about your documents…")
        if prompt:
            st.session_state.messages.append({"role": "user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)

            with st.chat_message("assistant"):
                placeholder = st.empty()
                typing = st.empty()
                typing.markdown("▌")
                full = ""
                done_event: dict[str, Any] = {}
                try:
                    for event in client().chat_stream(
                        prompt, session_id=st.session_state.session_id
                    ):
                        if event.get("event") == "meta":
                            if event.get("session_id"):
                                st.session_state.session_id = event["session_id"]
                            st.session_state.last_sources = (
                                event.get("retrieved_chunks")
                                or event.get("sources")
                                or []
                            )
                        elif event.get("event") == "token":
                            full += event.get("content") or ""
                            placeholder.markdown(full + "▌")
                        elif event.get("event") == "done":
                            done_event = event
                            full = event.get("answer") or full
                            placeholder.markdown(full)
                        elif event.get("event") == "error":
                            raise RuntimeError(event.get("content") or "Chat failed")
                    typing.empty()
                except Exception as exc:
                    typing.empty()
                    placeholder.error(str(exc))
                    full = f"Error: {exc}"

                assistant_msg = {
                    "id": done_event.get("message_id"),
                    "role": "assistant",
                    "content": full,
                    "confidence": done_event.get("confidence"),
                    "sources": done_event.get("sources") or st.session_state.last_sources,
                    "cached": done_event.get("cached", False),
                    "rating": "none",
                }
                st.session_state.messages.append(assistant_msg)
                if done_event.get("sources"):
                    st.session_state.last_sources = done_event["sources"]
                st.rerun()

        if st.session_state.session_id:
            try:
                pdf_bytes = client().export_pdf(st.session_state.session_id)
                st.download_button(
                    "Download conversation as PDF",
                    data=pdf_bytes,
                    file_name=f"chat-{st.session_state.session_id[:8]}.pdf",
                    mime="application/pdf",
                )
            except Exception:
                pass

    with right:
        st.markdown("### Retrieved sources")
        sources = st.session_state.last_sources or []
        if not sources:
            st.caption("Sources from the latest answer appear here.")
        for s in sources:
            st.markdown(
                f"""
                <div class="source-box">
                  <strong>{s.get('filename', 'doc')}</strong>
                  · p.{s.get('page_number', '?')}
                  · score {(float(s.get('score', 0)) * 100):.0f}%
                  <br/>{s.get('content', '')[:500]}{'…' if len(s.get('content', '')) > 500 else ''}
                </div>
                """,
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Admin page
# ---------------------------------------------------------------------------
def render_admin() -> None:
    st.markdown("## Admin dashboard")
    if st.button("Refresh stats"):
        st.rerun()
    try:
        stats = client().admin_stats()
    except Exception as exc:
        st.error(f"Could not load stats: {exc}")
        return

    docs = stats.get("documents") or {}
    cols = st.columns(5)
    metrics = [
        ("Documents", docs.get("total_documents")),
        ("Pages", docs.get("total_pages")),
        ("Chunks", docs.get("total_chunks")),
        ("Sessions", stats.get("total_sessions")),
        ("Tokens", stats.get("total_tokens_used")),
    ]
    for col, (label, value) in zip(cols, metrics):
        col.metric(label, value if value is not None else "—")

    c1, c2, c3 = st.columns(3)
    c1.metric("Indexed docs", docs.get("indexed_documents"))
    c2.metric("Cache hits", stats.get("cache_hits"))
    c3.metric("Cache misses", stats.get("cache_misses"))
    c1.metric("Storage (bytes)", docs.get("total_size_bytes"))
    c2.metric("Messages", stats.get("total_messages"))

    try:
        health = client().health()
        st.success(
            f"API healthy · provider=`{health.get('llm_provider')}` · {health.get('app')}"
        )
    except Exception as exc:
        st.error(f"API health check failed: {exc}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    init_state()
    apply_theme()
    render_sidebar()

    if st.session_state.page == "Admin":
        render_admin()
    else:
        render_chat()


if __name__ == "__main__":
    main()
