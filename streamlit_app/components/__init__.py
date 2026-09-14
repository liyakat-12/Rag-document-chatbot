"""Shared Streamlit helpers."""

from __future__ import annotations

from html import escape
from typing import Any


STAGE_LABELS = {
    "uploaded": "File uploaded",
    "extracted": "Text extracted",
    "cleaned": "Text cleaned",
    "chunked": "Chunks created",
    "embedded_faiss": "Embeddings generated · FAISS updated",
    "bm25_updated": "BM25 index updated",
    "failed": "Indexing failed",
}


def fmt_bytes(n: int) -> str:
    mb = n / (1024 * 1024)
    if mb >= 1:
        return f"{mb:.1f} MB"
    return f"{n / 1024:.0f} KB"


def fmt_status(status: str) -> tuple[str, str]:
    s = (status or "").lower()
    if s == "indexed":
        return "Indexed", "status-ok"
    if s in {"pending", "indexing"}:
        return "Indexing", "status-warn"
    if s == "error":
        return "Failed", "status-err"
    return status.title() if status else "Unknown", "status-warn"


def confidence_bar(confidence: float | None) -> str:
    if confidence is None:
        return ""
    pct = max(0, min(100, int(round(float(confidence) * 100))))
    return (
        f'<div style="margin:.35rem 0 .55rem;">'
        f'<span class="meta-chip">Grounding confidence {pct}%</span>'
        f'<div class="conf-bar"><span style="width:{pct}%;"></span></div>'
        f'<div style="font-size:.72rem;color:var(--dm-muted);">Heuristic score from retrieval strength</div>'
        f"</div>"
    )


def render_markdown_safe(text: str) -> str:
    """Escape HTML but preserve newlines for display wrappers."""
    return escape(text or "").replace("\n", "<br/>")


def friendly_error(exc: Exception | str) -> str:
    msg = str(exc)
    lower = msg.lower()
    if "insufficient_quota" in lower or "429" in lower or "rate limit" in lower:
        return (
            "AI generation is temporarily unavailable (provider quota/rate limit). "
            "Try again later, or set LLM_PROVIDER=extractive in .env."
        )
    if "401" in lower or "invalid_api_key" in lower or "authentication" in lower:
        return "AI provider authentication failed. Check OPENAI_API_KEY in .env."
    if "connection" in lower or "connect" in lower or "refused" in lower:
        return "The API is unavailable. Start the backend or check the API URL in Settings."
    if "413" in lower or "too large" in lower:
        return "That file exceeds the upload size limit (40 MB)."
    if "not a valid pdf" in lower or "invalid pdf" in lower or "magic" in lower:
        return "That file does not look like a valid PDF."
    if "empty" in lower and "pdf" in lower:
        return "This PDF has no extractable text."
    if "500" in lower:
        return "The server hit an unexpected error. Try again, or check backend logs."
    if "Traceback" in msg:
        return "Something went wrong while processing your request."
    return msg[:280]
