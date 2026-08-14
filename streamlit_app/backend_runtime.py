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

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000


def _port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


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


def start_backend(host: str = BACKEND_HOST, port: int = BACKEND_PORT, timeout: float = 90.0) -> None:
    """Start the FastAPI backend (uvicorn) in a daemon thread, once per process."""
    if _port_open(host, port):
        return  # Already running

    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    os.chdir(PROJECT_ROOT)  # keep relative paths (e.g. sqlite db) consistent with local dev

    _apply_secrets_to_env()

    import uvicorn

    from backend.app.main import app as fastapi_app

    def _run() -> None:
        uvicorn.run(fastapi_app, host=host, port=port, log_level="warning")

    threading.Thread(target=_run, daemon=True, name="fastapi-backend").start()

    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open(host, port):
            return
        time.sleep(0.25)
    raise RuntimeError(
        f"Backend did not start on {host}:{port} within {timeout:.0f}s. "
        "Check the app logs for a startup error."
    )
