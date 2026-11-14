"""DocuMind AI theme — load styles.css tokens + structure.

Light/dark sets live in ``styles.css`` inside ``@@tokens:*`` blocks.
``apply_theme(dark)`` injects the active token set plus shared structure.
"""

from __future__ import annotations

import re
from pathlib import Path

_CSS_PATH = Path(__file__).resolve().parent / "styles.css"

_TOKEN_RE = re.compile(
    r"/\* @@tokens:(light|dark) \*/(.*?)/\* @@/tokens:\1 \*/",
    re.S,
)
_STRUCTURE_RE = re.compile(
    r"/\* @@structure \*/(.*?)/\* @@/structure \*/",
    re.S,
)
_DARK_OVERRIDES_RE = re.compile(
    r"/\* @@dark-overrides \*/(.*?)/\* @@/dark-overrides \*/",
    re.S,
)


def _read_css() -> str:
    return _CSS_PATH.read_text(encoding="utf-8")


def _section(pattern: re.Pattern[str], css: str, *, group: int = 1) -> str:
    m = pattern.search(css)
    if not m:
        return ""
    return m.group(group).strip()


def _tokens(css: str, mode: str) -> str:
    for m in _TOKEN_RE.finditer(css):
        if m.group(1) == mode:
            return m.group(2).strip()
    return ""


def apply_theme(dark: bool) -> str:
    """Return injected <style> for the active appearance (sidebar toggle)."""
    css = _read_css()
    mode = "dark" if dark else "light"
    parts = [
        _tokens(css, mode),
        _section(_STRUCTURE_RE, css),
    ]
    if dark:
        parts.append(_section(_DARK_OVERRIDES_RE, css))
    body = "\n".join(p for p in parts if p)
    return f"<style>\n{body}\n</style>"
