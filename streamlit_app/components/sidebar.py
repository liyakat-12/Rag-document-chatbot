"""Sidebar — brand, navigation, library snapshot, recent chats."""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

import components._pathfix  # noqa: F401
from components import fmt_status, friendly_error

NAV_PAGES = ["Chat", "Documents", "Analytics", "Settings", "About"]
_PAGE_WIDGET = "page_selector"


def _short_name(name: str, max_len: int = 28) -> str:
    name = (name or "document.pdf").strip()
    if len(name) <= max_len:
        return name
    stem, _, ext = name.rpartition(".")
    if stem and ext and len(ext) <= 4:
        keep = max_len - len(ext) - 2
        return f"{stem[:keep]}….{ext}"
    return name[: max_len - 1] + "…"


def _go(page: str) -> None:
    """Request navigation from an on_click callback (never touches the selectbox key)."""
    if page in NAV_PAGES:
        st.session_state.page = page
        st.session_state["_force_page"] = page


def _render_health() -> None:
    status = st.session_state.get("backend_status") or (
        "connected" if st.session_state.get("backend_ok") else "unavailable"
    )
    provider = st.session_state.get("llm_provider") or "—"

    if status == "checking":
        st.markdown(
            '<span class="meta-chip health-warn">Checking…</span>',
            unsafe_allow_html=True,
        )
    elif status == "connected":
        st.markdown(
            f'<span class="meta-chip health-ok">Connected</span> '
            f'<span class="meta-chip">{provider}</span>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<span class="meta-chip health-err">Unavailable</span>',
            unsafe_allow_html=True,
        )
        st.caption(
            "Chat, upload, and analytics need the API. "
            "Start `run_documind.bat` or `run_backend.bat`, then refresh."
        )
        if st.button("Retry connection", key="health_retry", use_container_width=True):
            st.session_state["_force_health_refresh"] = True
            st.rerun()


def render_sidebar(
    client_factory: Callable[[], Any],
    *,
    on_new_chat: Callable[[], None],
    on_load_session: Callable[[str], None],
) -> None:
    with st.sidebar:
        # Rebind selectbox BEFORE it is instantiated (button nav from prior run)
        force = st.session_state.pop("_force_page", None)
        if force in NAV_PAGES:
            st.session_state.page = force
            st.session_state[_PAGE_WIDGET] = force

        current = st.session_state.get("page") or "Chat"
        if current not in NAV_PAGES:
            current = "Chat"
            st.session_state.page = current
        if _PAGE_WIDGET not in st.session_state:
            st.session_state[_PAGE_WIDGET] = current

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
        _render_health()

        st.markdown('<div class="divider-soft"></div>', unsafe_allow_html=True)
        st.markdown('<p class="nav-hint">Workspace</p>', unsafe_allow_html=True)

        choice = st.selectbox(
            "Page",
            NAV_PAGES,
            key=_PAGE_WIDGET,
            label_visibility="collapsed",
        )
        st.session_state.page = choice

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
        st.button(
            "Manage documents",
            use_container_width=True,
            on_click=_go,
            args=("Documents",),
        )
        for d in docs[:4]:
            full = d.get("original_filename") or "document.pdf"
            name = _short_name(full)
            label, _ = fmt_status(d.get("status", ""))
            # Truncate visually; full name shown when short enough to fit
            tip = f" ({full})" if name != full else ""
            st.caption(f"• {name} — {label}{tip if len(full) <= 48 else ''}")

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
            for s in sessions[:5]:
                full_title = s.get("title") or "Untitled"
                title = _short_name(full_title, 32)
                sid = s["id"]
                confirm_key = f"confirm_del_sess_{sid}"

                def _load(session_id: str = sid) -> None:
                    on_load_session(session_id)
                    _go("Chat")

                c1, c2 = st.columns([5, 1])
                with c1:
                    st.button(
                        title,
                        key=f"sess_{sid}",
                        use_container_width=True,
                        on_click=_load,
                        help=full_title if title != full_title else "Open conversation",
                    )
                with c2:
                    if st.session_state.get(confirm_key):
                        if st.button("✓", key=f"yes_sess_{sid}", help="Confirm delete"):
                            try:
                                client_factory().delete_session(sid)
                                st.session_state.pop(confirm_key, None)
                                if st.session_state.get("session_id") == sid:
                                    on_new_chat()
                                st.rerun()
                            except Exception as exc:
                                st.session_state["_sidebar_error"] = friendly_error(exc)
                        if st.button("↩", key=f"no_sess_{sid}", help="Cancel"):
                            st.session_state.pop(confirm_key, None)
                            st.rerun()
                    else:
                        if st.button("✕", key=f"del_sess_{sid}", help="Delete conversation"):
                            st.session_state[confirm_key] = True
                            st.rerun()

        err = st.session_state.pop("_sidebar_error", None)
        if err:
            st.error(err)

        # Button callbacks run when their widget is created (after the selectbox).
        # If they changed page, rebind the selectbox on a clean rerun.
        if st.session_state.get("page") != choice and st.session_state.get("page") in NAV_PAGES:
            st.session_state["_force_page"] = st.session_state.page
            st.rerun()
