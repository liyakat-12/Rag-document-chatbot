"""Sidebar — brand, new chat, documents snapshot, conversations, settings nav."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import streamlit as st

import components._pathfix  # noqa: F401
from components import fmt_status, friendly_error

NAV_PAGES = ["Chat", "Documents", "Analytics", "Settings", "About"]


def render_sidebar(
    client_factory: Callable[[], Any],
    *,
    on_new_chat: Callable[[], None],
    on_load_session: Callable[[str], None],
) -> None:
    with st.sidebar:
        st.markdown('<p class="brand-title">DocuMind AI</p>', unsafe_allow_html=True)
        st.markdown(
            '<p class="brand-tag">Ask your documents. Get grounded answers.</p>',
            unsafe_allow_html=True,
        )

        st.session_state.page = st.radio(
            "Navigation",
            NAV_PAGES,
            index=NAV_PAGES.index(st.session_state.get("page", "Chat"))
            if st.session_state.get("page", "Chat") in NAV_PAGES
            else 0,
            label_visibility="collapsed",
        )
        st.toggle("Dark mode", key="dark_mode")

        if st.button("+ New Chat", type="primary", use_container_width=True):
            on_new_chat()
            st.session_state.page = "Chat"
            st.rerun()

        # --- Documents snapshot ---
        st.markdown('<p class="nav-hint">Documents</p>', unsafe_allow_html=True)
        try:
            docs = client_factory().list_documents()
        except Exception:
            docs = []
        indexed = sum(1 for d in docs if (d.get("status") or "").lower() == "indexed")
        st.caption(f"{indexed} indexed · {len(docs)} total")
        if st.button("Manage documents", use_container_width=True):
            st.session_state.page = "Documents"
            st.rerun()
        for d in docs[:5]:
            name = d.get("original_filename") or "document.pdf"
            label, _ = fmt_status(d.get("status", ""))
            st.caption(f"• {name[:34]} — {label}")

        # --- Conversations ---
        st.markdown('<p class="nav-hint">Conversations</p>', unsafe_allow_html=True)
        try:
            sessions = client_factory().list_sessions()
        except Exception as exc:
            st.caption(friendly_error(exc))
            sessions = []

        if not sessions:
            st.caption("No conversations yet.")

        for s in sessions[:20]:
            title = (s.get("title") or "Untitled")[:42]
            updated = s.get("updated_at") or s.get("created_at") or ""
            stamp = ""
            if updated:
                try:
                    dt = datetime.fromisoformat(str(updated).replace("Z", "+00:00"))
                    stamp = dt.strftime("%b %d · %H:%M")
                except Exception:
                    stamp = str(updated)[:16]

            c1, c2 = st.columns([5, 1])
            with c1:
                if st.button(title, key=f"sess_{s['id']}", use_container_width=True):
                    on_load_session(s["id"])
                    st.session_state.page = "Chat"
                    st.rerun()
                if stamp:
                    st.caption(stamp)
            with c2:
                if st.button("×", key=f"del_sess_{s['id']}", help="Delete conversation"):
                    try:
                        client_factory().delete_session(s["id"])
                        if st.session_state.session_id == s["id"]:
                            on_new_chat()
                        st.rerun()
                    except Exception as exc:
                        st.error(friendly_error(exc))

        # --- Settings snapshot ---
        st.markdown('<p class="nav-hint">Settings</p>', unsafe_allow_html=True)
        provider = st.session_state.get("llm_provider") or "—"
        st.caption(f"LLM · `{provider}`")
        if st.button("Open settings", use_container_width=True):
            st.session_state.page = "Settings"
            st.rerun()
