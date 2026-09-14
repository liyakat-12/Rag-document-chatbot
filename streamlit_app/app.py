"""
DocuMind AI — Streamlit frontend
Run: streamlit run streamlit_app/app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import streamlit as st

# Ensure streamlit_app/ is importable regardless of launch cwd
_APP_DIR = Path(__file__).resolve().parent
if str(_APP_DIR) not in sys.path:
    sys.path.insert(0, str(_APP_DIR))

from api_client import RagClient
from backend_runtime import discover_rag_base, start_backend
from components.about import render_about
from components.analytics import render_analytics
from components.chat import render_chat
from components.documents import render_documents
from components.settings import render_settings
from components.sidebar import render_sidebar
from styles.theme import apply_theme


@st.cache_resource(show_spinner="Starting backend service…")
def _bootstrap_backend() -> str:
    return start_backend()


API_BASE = _bootstrap_backend()
_env = (os.getenv("VITE_API_BASE_URL") or os.getenv("API_BASE_URL") or "").strip()
if _env:
    API_BASE = _env.rstrip("/")
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
    st.session_state.api_base = API_BASE
    return RagClient(base_url=API_BASE)


def init_state() -> None:
    defaults: dict[str, Any] = {
        "session_id": None,
        "messages": [],
        "dark_mode": False,
        "page": "Chat",
        "pending_prompt": None,
        "last_ingest_stages": None,
        "llm_provider": "",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


def new_chat() -> None:
    st.session_state.session_id = None
    st.session_state.messages = []
    st.session_state.pending_prompt = None


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


def _refresh_provider() -> None:
    try:
        health = client().health()
        st.session_state.llm_provider = health.get("llm_provider") or ""
    except Exception:
        pass


def main() -> None:
    init_state()
    st.markdown(apply_theme(bool(st.session_state.get("dark_mode"))), unsafe_allow_html=True)
    _refresh_provider()

    render_sidebar(client, on_new_chat=new_chat, on_load_session=load_session)

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
