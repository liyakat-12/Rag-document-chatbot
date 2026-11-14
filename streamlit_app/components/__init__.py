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


def truncate_at_word(text: str, max_len: int = 28) -> str:
    """Cut at a word boundary; never mid-word."""
    text = (text or "").strip()
    if len(text) <= max_len:
        return text
    cut = text[: max_len - 1]
    if " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(".,;:/-_") + "…"


def fmt_status(status: str) -> tuple[str, str]:
    s = (status or "").lower()
    if s == "indexed":
        return "Indexed", "status-ok"
    if s in {"pending", "indexing"}:
        return "Indexing", "status-warn"
    if s == "error":
        return "Failed", "status-err"
    return status.title() if status else "Unknown", "status-warn"


def status_dot_class(status: str) -> str:
    s = (status or "").lower()
    if s == "indexed":
        return "ok"
    if s in {"pending", "indexing"}:
        return "warn"
    if s == "error":
        return "err"
    return "warn"


def confidence_label(confidence: float | None) -> str:
    """Descriptive evidence band from the retrieval-strength heuristic."""
    if confidence is None:
        return "Unknown evidence"
    c = float(confidence)
    if c <= 0:
        return "Insufficient evidence"
    if c < 0.45:
        return "Limited evidence"
    if c < 0.75:
        return "Moderate evidence"
    return "Strong evidence"


def confidence_badge(n_documents: int = 1) -> str:
    """User-facing plain badge (no scores / percentages)."""
    n = max(0, int(n_documents or 0))
    label = f"Found in {n} document" if n == 1 else f"Found in {n} documents"
    return (
        f'<div style="margin:.35rem 0 .55rem;">'
        f'<span class="meta-chip evidence-strong">{label}</span>'
        f"</div>"
    )


def confidence_bar(confidence: float | None) -> str:
    """Developer-mode retrieval strength details (scores + heuristic %)."""
    if confidence is None:
        return ""
    c = float(confidence)
    if c <= 0:
        return ""
    label = confidence_label(confidence)
    css = (
        "evidence-strong"
        if c >= 0.75
        else "evidence-limited"
        if c >= 0.45
        else "evidence-none"
    )
    pct = max(0, min(100, int(round(c * 100))))
    return (
        f'<div style="margin:.35rem 0 .55rem;">'
        f'<span class="meta-chip {css}">{label}</span>'
        f'<div class="conf-bar"><span style="width:{pct}%;"></span></div>'
        f'<div style="font-size:.72rem;color:var(--dm-text-muted);">'
        f'Retrieval strength heuristic ({pct}%) from fused FAISS+BM25 scores — '
        f'not a calibrated probability of correctness'
        f"</div>"
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
