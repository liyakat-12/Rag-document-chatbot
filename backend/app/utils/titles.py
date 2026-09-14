"""Helpers for human-readable conversation titles."""

from __future__ import annotations

import re


def make_conversation_title(text: str, max_len: int = 72) -> str:
    """
    Build a clean sidebar title from the first user question.

    Examples:
      "what is candidates name?" → "What is candidates name?"
      long text is truncated with an ellipsis
    """
    cleaned = " ".join((text or "").strip().split())
    if not cleaned:
        return "New Chat"
    # Strip wrapping quotes
    cleaned = cleaned.strip("\"'")
    # Sentence-case first character
    cleaned = cleaned[0].upper() + cleaned[1:]
    # Soften multiple punctuation
    cleaned = re.sub(r"[?]{2,}", "?", cleaned)
    if len(cleaned) > max_len:
        cleaned = cleaned[: max_len - 1].rstrip() + "…"
    return cleaned
