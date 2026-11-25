"""Sidebar — brand, navigation, library snapshot, recent chats."""

from __future__ import annotations

from html import escape
from typing import Any, Callable

import streamlit as st

import components._pathfix  # noqa: F401
from components import friendly_error, status_dot_class, truncate_at_word

# Primary nav labels → page keys
_NAV_PRIMARY = [
    ("Chat", "Chat", "💬"),
    ("Library", "Documents", "📚"),
    ("About", "About", "ℹ"),
]
_NAV_MORE = [
    ("Analytics", "Analytics"),
    ("Settings", "Settings"),
]


def _go(page: str) -> None:
    st.session_state.page = page
    st.session_state["_force_page"] = page


def _render_status_dot() -> None:
    status = st.session_state.get("backend_status") or (
        "connected" if st.session_state.get("backend_ok") else "unavailable"
    )
    provider = st.session_state.get("llm_provider") or "—"
    if status == "checking":
        css, label, tip = "is-checking", "Checking", "Probing the API…"
    elif status == "connected":
        offline = provider == "extractive"
        css = "is-offline" if offline else "is-offline"
        label = "Offline" if offline else "Online"
        tip = (
            f"Backend connected · provider={provider}. "
            "Details in Settings."
            if not offline
            else "Offline extractive mode — answers from retrieved passages only. "
            "Change LLM_PROVIDER in Settings / .env."
        )
    else:
        css, label, tip = (
            "is-down",
            "Unavailable",
            "API unreachable. Start the backend, then retry in Settings.",
        )
    st.markdown(
        f'<div class="status-dot {css}" title="{escape(tip)}">{escape(label)}</div>',
        unsafe_allow_html=True,
    )


def render_sidebar(
    client_factory: Callable[[], Any],
    *,
    on_new_chat: Callable[[], None],
    on_load_session: Callable[[str], None],
) -> None:
    with st.sidebar:
        force = st.session_state.pop("_force_page", None)
        if force:
            st.session_state.page = force

        current = st.session_state.get("page") or "Chat"

        st.markdown(
            """
            <div class="brand-mark">
              <div class="logo">D</div>
              <div>
                <p class="brand-title">DocuMind AI</p>
              </div>
            </div>
            <p class="brand-tag">Private PDFs. Grounded answers. Citations you can verify.</p>
            """,
            unsafe_allow_html=True,
        )
        _render_status_dot()

        st.markdown('<div class="divider-soft"></div>', unsafe_allow_html=True)
        st.markdown('<p class="nav-hint">Navigate</p>', unsafe_allow_html=True)

        for label, page, icon in _NAV_PRIMARY:
            active = "active" if current == page else ""
            st.markdown(f'<div class="nav-link-btn {active}">', unsafe_allow_html=True)
            if st.button(
                f"{icon}  {label}",
                key=f"nav_{page}",
                use_container_width=True,
                on_click=_go,
                args=(page,),
            ):
                pass
            st.markdown("</div>", unsafe_allow_html=True)

        with st.expander("More", expanded=False):
            for label, page in _NAV_MORE:
                if st.button(label, key=f"nav_more_{page}", use_container_width=True):
                    _go(page)
                    st.rerun()

        st.toggle("Dark mode", key="dark_mode")

        def _new_chat() -> None:
            on_new_chat()
            _go("Chat")

        st.button(
            "New chat",
            type="primary",
            use_container_width=True,
            on_click=_new_chat,
        )

        st.markdown('<p class="nav-hint">Library</p>', unsafe_allow_html=True)
        try:
            docs = client_factory().list_documents() if st.session_state.get("backend_ok") else []
        except Exception:
            docs = []
        indexed = sum(1 for d in docs if (d.get("status") or "").lower() == "indexed")
        st.caption(f"{indexed} indexed · {len(docs)} total")
        if st.button("Manage documents", use_container_width=True):
            _go("Documents")
            st.rerun()
        for d in docs[:6]:
            full = d.get("original_filename") or "document.pdf"
            name = truncate_at_word(full, 26)
            dot = status_dot_class(d.get("status", ""))
            st.markdown(
                f'<div class="lib-row" title="{escape(full)}">'
                f'<span class="lib-dot {dot}"></span>'
                f"<span>{escape(name)}</span></div>",
                unsafe_allow_html=True,
            )

        try:
            sessions = (
                client_factory().list_sessions() if st.session_state.get("backend_ok") else []
            )
        except Exception as exc:
            st.caption(friendly_error(exc))
            sessions = []

        st.markdown('<p class="nav-hint">Recent</p>', unsafe_allow_html=True)
        if not sessions:
            st.caption("No conversations yet.")
        else:
            for s in sessions[:6]:
                full_title = s.get("title") or "Untitled"
                title = truncate_at_word(full_title, 30)
                sid = s["id"]

                def _load(session_id: str = sid) -> None:
                    on_load_session(session_id)
                    _go("Chat")

                st.markdown('<div class="sess-row">', unsafe_allow_html=True)
                st.button(
                    title,
                    key=f"sess_{sid}",
                    use_container_width=True,
                    on_click=_load,
                    help=full_title,
                )
                st.markdown("</div>", unsafe_allow_html=True)

        err = st.session_state.pop("_sidebar_error", None)
        if err:
            st.error(err)
