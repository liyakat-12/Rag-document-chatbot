"""Extract document headings for starter questions (UI-only, local PDF)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Sequence

_HEADING_LINE = re.compile(
    r"^(?:"
    r"[A-Z][A-Z0-9 /&\-]{2,40}"  # ALL CAPS section
    r"|[A-Z][a-zA-Z0-9]+(?: [A-Z][a-zA-Z0-9]+){0,6}"  # Title Case
    r")$"
)
_SKIP = {
    "page", "confidential", "draft", "contents", "table of contents",
    "continued", "documind",
}


def _upload_roots() -> list[Path]:
    roots: list[Path] = []
    here = Path(__file__).resolve()
    # streamlit_app/components → repo root
    repo = here.parents[2]
    for rel in ("data/uploads", "uploads", "evals/corpus/real"):
        p = (repo / rel).resolve()
        if p.is_dir():
            roots.append(p)
    return roots


def resolve_pdf_path(doc: dict[str, Any]) -> Path | None:
    """Find stored PDF by DocumentOut.filename or original_filename."""
    stored = (doc.get("filename") or "").strip()
    original = (doc.get("original_filename") or "").strip()
    for root in _upload_roots():
        if stored:
            cand = root / stored
            if cand.is_file():
                return cand
        if original:
            # {uuid}_{safe_name}
            for p in root.glob(f"*_{original}"):
                if p.is_file():
                    return p
            direct = root / original
            if direct.is_file():
                return direct
    # Eval / fixture corpus by original name
    repo = Path(__file__).resolve().parents[2]
    for folder in (
        repo / "evals" / "corpus" / "real",
        repo / "tests" / "fixtures",
    ):
        if not folder.is_dir():
            continue
        if original and (folder / original).is_file():
            return folder / original
    return None


def extract_headings(pdf_path: Path, *, limit: int = 8) -> list[str]:
    """Prefer PDF outline (TOC); fall back to short title-like lines on page 1–2."""
    headings: list[str] = []
    try:
        import fitz

        doc = fitz.open(pdf_path)
        try:
            for _lvl, title, _page in doc.get_toc() or []:
                t = " ".join((title or "").split()).strip(" .:-")
                if t and t.lower() not in _SKIP and 2 < len(t) < 60:
                    headings.append(t)
            if not headings:
                for page_i in range(min(2, doc.page_count)):
                    text = doc.load_page(page_i).get_text("text") or ""
                    for line in text.splitlines():
                        line = " ".join(line.split()).strip(" .:-")
                        if not line or len(line) < 3 or len(line) > 48:
                            continue
                        if line.lower() in _SKIP:
                            continue
                        if _HEADING_LINE.match(line) or line.endswith(":"):
                            headings.append(line.rstrip(":"))
        finally:
            doc.close()
    except Exception:
        return []
    # Dedupe preserve order
    seen: set[str] = set()
    out: list[str] = []
    for h in headings:
        key = h.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(h)
        if len(out) >= limit:
            break
    return out


def starter_questions_from_headings(
    headings: Sequence[str],
    *,
    doc_name: str = "",
) -> list[str]:
    """Build extractive-friendly questions from headings."""
    qs: list[str] = []
    if doc_name:
        qs.append(f"What is {doc_name} about?")
    for h in headings[:4]:
        qs.append(f"What does the document say under “{h}”?")
    # Keep two stable extractive anchors if few headings
    if len(qs) < 4:
        qs.append("List the main section headings in this document.")
    if len(qs) < 4:
        qs.append("What names, dates, or numbers appear near the start?")
    return qs[:4]


def starters_for_docs(docs: list[dict[str, Any]]) -> list[str]:
    """Starters for scoped docs (or all indexed if unscoped)."""
    if not docs:
        return [
            "What is this document about?",
            "List the main section headings in this document.",
            "What names, dates, or numbers appear near the start?",
            "Which sections cover skills or experience?",
        ]
    # Prefer single selected / first doc
    target = docs[0]
    name = (target.get("original_filename") or "this document").rsplit(".", 1)[0]
    path = resolve_pdf_path(target)
    headings = extract_headings(path) if path else []
    return starter_questions_from_headings(headings, doc_name=name)
