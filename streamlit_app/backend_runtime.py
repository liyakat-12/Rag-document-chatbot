"""
Boots the FastAPI backend in-process for single-service deployments
(e.g. Streamlit Community Cloud) where only one port can be exposed.

Locally, running the backend separately via `uvicorn backend.app.main:app`
is still the normal / recommended workflow — this module is only needed
when the Streamlit app must be fully self-contained.
"""

from __future__ import annotations

import os
import socket
import sys
import threading
import time
from pathlib import Path

import httpx

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_HOST = "127.0.0.1"
BACKEND_PORTS = (8000, 8001)


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


def is_rag_backend(base_url: str) -> bool:
    """True only if this API is our RAG Document Chatbot (not another app)."""
    try:
        with httpx.Client(timeout=2.0) as client:
            health = client.get(f"{base_url.rstrip('/')}/health")
            if health.status_code != 200:
                return False
            data = health.json()
            app_name = str(data.get("app") or "")
            if app_name in {"DocuMind AI", "DocuMind RAG", "RAG Document Chatbot"}:
                return True
            if data.get("retrieval_strategy") == "hybrid_rrf":
                return True
            # MediAssist and similar apps also expose /health but not /history
            hist = client.get(f"{base_url.rstrip('/')}/history")
            return hist.status_code == 200
    except Exception:
        return False


def discover_rag_base(host: str = BACKEND_HOST) -> str | None:
    """Return the first live RAG API base URL, if any."""
    for port in BACKEND_PORTS:
        url = f"http://{host}:{port}/api/v1"
        if is_rag_backend(url):
            return url
    return None


def _apply_secrets_to_env() -> None:
    """Bridge Streamlit Cloud secrets into environment variables and fall
    back to free/offline defaults so the app works with zero configuration.
    Must run before backend.app.config is imported anywhere (it caches
    settings on first import)."""
    try:
        import streamlit as st

        for key, value in dict(st.secrets).items():
            os.environ.setdefault(key.upper(), str(value))
    except Exception:
        pass

    os.environ.setdefault("LLM_PROVIDER", "extractive")
    os.environ.setdefault("EMBEDDING_PROVIDER", "local")


def start_backend(host: str = BACKEND_HOST, timeout: float = 90.0) -> str:
    """
    Ensure a RAG backend is reachable.
    Returns the API base URL (e.g. http://127.0.0.1:8001/api/v1).
    """
    existing = discover_rag_base(host)
    if existing:
        return existing

    # Prefer a free port; skip ports occupied by unrelated apps
    port = None
    for candidate in BACKEND_PORTS:
        if not _port_open(host, candidate):
            port = candidate
            break
    if port is None:
        raise RuntimeError(
            "Ports 8000 and 8001 are both in use, but neither is the RAG Document Chatbot. "
            "Stop the other service or set API_BASE_URL to the correct RAG backend."
        )

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    os.chdir(PROJECT_ROOT)

    _apply_secrets_to_env()

    import uvicorn

    from backend.app.main import app as fastapi_app

    def _run() -> None:
        uvicorn.run(fastapi_app, host=host, port=port, log_level="warning")

    threading.Thread(target=_run, daemon=True, name="fastapi-backend").start()

    base = f"http://{host}:{port}/api/v1"
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_rag_backend(base):
            return base
        time.sleep(0.25)
    raise RuntimeError(
        f"RAG backend did not start on {host}:{port} within {timeout:.0f}s. "
        "Check the app logs for a startup error."
    )
