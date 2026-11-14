"""Text cleaning helpers for PDF-extracted content."""

from __future__ import annotations

import re


def fix_hyphenation(text: str) -> str:
    """Join line-break hyphens and spaced mid-word hyphens (e.g. hands -on → hands-on).

    Used when ``ingest.fix_hyphenation`` is enabled (default off).
    """
    if not text:
        return ""
    text = text.replace("\u00ad", "")  # soft hyphen
    # Line-break hyphenation: "exam-\nple" / "exam- \nple"
    text = re.sub(r"(\w)-\s*\n\s*(\w)", r"\1\2", text)
    # Spaced hyphen inside a compound: "hands -on" / "hands- on"
    text = re.sub(r"(\w)\s+-\s*(\w)", r"\1-\2", text)
    text = re.sub(r"(\w)-\s+(\w)", r"\1-\2", text)
    return text


def clean_text(text: str, *, fix_hyphens: bool = False) -> str:
    """Normalize whitespace and remove common PDF extraction artifacts."""
    if not text:
        return ""
    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if fix_hyphens:
        text = fix_hyphenation(text)
    else:
        # Legacy default: only join hyphen+newline (unchanged for snapshot/index)
        text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # Collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Collapse horizontal whitespace
    text = re.sub(r"[ \t]+", " ", text)
    # Strip null bytes and control chars (except newline/tab)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    return text.strip()
