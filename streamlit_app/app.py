"""
DocuMind AI — Streamlit frontend
Run: streamlit run streamlit_app/app.py
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import Any

import streamlit as st

# Ensure streamlit_app/ is importable regardless of launch cwd
_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from api_client import RagClient
from backend_runtime import discover_rag_base, is_rag_backend, start_backend
from components.about import render_about
from components.analytics import render_analytics
from components.chat import render_chat
from components.documents import render_documents
from components.settings import render_settings
from components.sidebar import render_sidebar
from styles.theme import apply_theme

# Brief cache when healthy; shorter when down so recovery is noticed quickly
_HEALTH_TTL_OK = 20.0
_HEALTH_TTL_FAIL = 5.0


@st.cache_resource(show_spinner="Starting backend service…")
def _bootstrap_backend() -> str:
    return start_backend()


API_BASE = _bootstrap_backend()
_env = (os.getenv("VITE_API_BASE_URL") or os.getenv("API_BASE_URL") or "").strip()
if _env:
    candidate = _env.rstrip("/")
    # Never silently attach to a different app occupying the configured port
    if is_rag_backend(candidate):
        API_BASE = candidate
    elif not API_BASE:
        API_BASE = discover_rag_base() or "http://127.0.0.1:8001/api/v1"
elif not API_BASE:
    API_BASE = discover_rag_base() or "http://127.0.0.1:8001/api/v1"

MAX_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "40"))

st.set_page_config(
    page_title="DocuMind AI",
    page_icon="📄",
    layout="wide",
    initial_sidebar_state="expanded",
)


def client() -> RagClient:
    """Reuse one keep-alive HTTP client for the whole Streamlit session."""
    st.session_state.api_base = API_BASE
    existing = st.session_state.get("_rag_client")
    if existing is None or getattr(existing, "base_url", None) != API_BASE.rstrip("/"):
        if existing is not None:
            try:
                existing.close()
            except Exception:
                pass
        st.session_state._rag_client = RagClient(base_url=API_BASE)
    return st.session_state._rag_client


def init_state() -> None:
    defaults: dict[str, Any] = {
        "session_id": None,
        "messages": [],
        "dark_mode": False,
        "page": "Chat",
        "pending_prompt": None,
        "last_ingest_stages": None,
        "llm_provider": "",
        "selected_document_ids": [],
        "backend_ok": False,
        "backend_status": "checking",  # checking | connected | unavailable
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
    # Drop legacy nav widget keys from earlier sidebar implementations
    st.session_state.pop("nav", None)
    st.session_state.pop("page_selector", None)


def new_chat() -> None:
    st.session_state.session_id = None
    st.session_state.messages = []
    st.session_state.pending_prompt = None
    st.session_state.pop("last_failed_prompt", None)


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
            "retrieval": {},
            "timings": {},
        }
        for m in data.get("messages", [])
    ]
    st.session_state.pop("last_failed_prompt", None)


def _refresh_provider(*, force: bool = False) -> None:
    """Probe /health with short timeouts. Cache briefly; never treat UI as healthy backend."""
    now = time.time()
    last = float(st.session_state.get("_health_checked_at") or 0)
    was_ok = bool(st.session_state.get("backend_ok"))
    ttl = _HEALTH_TTL_OK if was_ok else _HEALTH_TTL_FAIL

    if not force and last and (now - last) < ttl:
        return

    st.session_state.backend_status = "checking"
    try:
        health = client().health()
        st.session_state.llm_provider = health.get("llm_provider") or ""
        st.session_state.backend_app = health.get("app") or "DocuMind AI"
        st.session_state.backend_error = None
        st.session_state.backend_detail = health.get("detail") or ""
        status = (health.get("status") or "").lower()
        ready = bool(health.get("ready"))
        if status == "starting" or (not ready and status not in {"ok", "degraded"}):
            st.session_state.backend_ok = False
            st.session_state.backend_status = "starting"
        elif status in {"ok", "ready"} or ready:
            st.session_state.backend_ok = True
            st.session_state.backend_status = "connected"
        elif status == "degraded":
            st.session_state.backend_ok = True  # API up; answers may be slow
            st.session_state.backend_status = "connected"
        else:
            st.session_state.backend_ok = ready
            st.session_state.backend_status = "connected" if ready else "starting"
        st.session_state._health_checked_at = now
    except Exception as exc:
        st.session_state.backend_ok = False
        st.session_state.backend_status = "unavailable"
        st.session_state.backend_error = str(exc)[:160]
        st.session_state._health_checked_at = now
        st.session_state.pop("_indexed_docs_cache", None)
        st.session_state.pop("_indexed_docs_cache_at", None)


def main() -> None:
    init_state()
    st.markdown(apply_theme(bool(st.session_state.get("dark_mode"))), unsafe_allow_html=True)
    force_health = bool(st.session_state.pop("_force_health_refresh", False))
    _refresh_provider(force=force_health)

    render_sidebar(client, on_new_chat=new_chat, on_load_session=load_session)

    if st.session_state.get("backend_status") == "starting":
        st.markdown(
            """
            <div class="hero-wrap">
              <p class="brand-hero">DocuMind AI</p>
              <p class="hero-title">Starting up</p>
              <p class="hero-sub">
                Loading the local search index. This usually takes a few seconds
                on first launch — hang tight.
              </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        detail = st.session_state.get("backend_detail") or ""
        if detail:
            st.caption(detail)
        st.info("The API is warming up. The page will unlock automatically.")
        import time as _time

        _time.sleep(1.5)
        st.rerun()
        return

    page = st.session_state.get("page", "Chat")
    if page == "Documents":
        render_documents(client, max_mb=MAX_MB)
    elif page == "Analytics":
        render_analytics(client)
    elif page == "Settings":
        render_settings(client, api_base=API_BASE)
    elif page == "About":
        render_about()
    else:
        render_chat(client, llm_provider=st.session_state.get("llm_provider") or "")


if __name__ == "__main__":
    main()
