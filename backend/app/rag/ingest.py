"""PDF loading, cleaning, and chunking."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document as LCDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.app.config import get_settings
from backend.app.utils.logging import get_logger
from backend.app.utils.text import clean_text
from backend.app.utils.tokens import count_tokens

logger = get_logger(__name__)

_LINE_RE = re.compile(r"[ \t]+\n")


def _page_lines(text: str) -> list[str]:
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    return [ln.strip() for ln in text.split("\n")]


def detect_repeated_header_footer_lines(
    pages: list[str],
    *,
    min_pages: int = 3,
    min_fraction: float = 0.4,
    edge_lines: int = 3,
) -> set[str]:
    """Return normalised lines that repeat across many pages (headers/footers).

    Only considers the first/last ``edge_lines`` non-empty lines of each page.
    Lines that appear on fewer than ``min_pages`` pages, or only once overall,
    are never returned.
    """
    if len(pages) < min_pages:
        return set()

    counts: Counter[str] = Counter()
    page_hits: dict[str, set[int]] = {}
    for pi, text in enumerate(pages):
        lines = [ln for ln in _page_lines(text) if ln]
        if not lines:
            continue
        edge: list[str] = []
        edge.extend(lines[:edge_lines])
        if len(lines) > edge_lines:
            edge.extend(lines[-edge_lines:])
        seen_on_page: set[str] = set()
        for ln in edge:
            key = re.sub(r"\s+", " ", ln).strip()
            if len(key) < 4 or key in seen_on_page:
                continue
            seen_on_page.add(key)
            counts[key] += 1
            page_hits.setdefault(key, set()).add(pi)

    threshold = max(min_pages, int(len(pages) * min_fraction))
    repeated: set[str] = set()
    for key, n in counts.items():
        if n < 2:
            continue  # never remove once-only lines
        if len(page_hits.get(key, ())) >= threshold or n >= threshold:
            repeated.add(key)
    return repeated


def strip_repeated_headers_footers(
    pages: list[LCDocument],
    *,
    min_pages: int = 3,
    min_fraction: float = 0.4,
) -> tuple[list[LCDocument], set[str]]:
    """Remove repeated header/footer lines from page documents. Returns (pages, removed)."""
    texts = [p.page_content or "" for p in pages]
    repeated = detect_repeated_header_footer_lines(
        texts, min_pages=min_pages, min_fraction=min_fraction
    )
    if not repeated:
        return pages, set()

    out: list[LCDocument] = []
    for page in pages:
        kept = []
        for ln in _page_lines(page.page_content or ""):
            key = re.sub(r"\s+", " ", ln).strip()
            if key and key in repeated:
                continue
            kept.append(ln)
        new_text = clean_text("\n".join(kept))
        out.append(
            LCDocument(page_content=new_text, metadata=dict(page.metadata))
        )
    logger.info(
        "headers_footers_stripped",
        removed=len(repeated),
        samples=list(repeated)[:3],
    )
    return out, repeated


def flag_low_text_pages(
    pages: list[LCDocument],
    *,
    char_threshold: int = 100,
) -> list[dict[str, Any]]:
    """Return metadata for pages below the character threshold (1-indexed)."""
    flagged: list[dict[str, Any]] = []
    for page in pages:
        raw_page = page.metadata.get("page", 0)
        page_number = int(raw_page) + 1 if isinstance(raw_page, int) else 1
        chars = len((page.page_content or "").strip())
        if chars < char_threshold:
            flagged.append({"page": page_number, "chars": chars, "threshold": char_threshold})
            page.metadata["low_text"] = True
            page.metadata["low_text_chars"] = chars
        else:
            page.metadata["low_text"] = False
    return flagged


def load_pdf(
    file_path: Path,
    *,
    strip_headers: Optional[bool] = None,
    flag_low_text: Optional[bool] = None,
    low_text_threshold: Optional[int] = None,
) -> list[LCDocument]:
    """Load a PDF and return LangChain documents (one per page).

    Optional ingest quality flags default to Settings (both off).
    """
    settings = get_settings()
    if strip_headers is None:
        strip_headers = bool(getattr(settings, "ingest_strip_repeated_headers_footers", False))
    if flag_low_text is None:
        flag_low_text = bool(getattr(settings, "ingest_flag_low_text_pages", False))
    if low_text_threshold is None:
        low_text_threshold = int(getattr(settings, "ingest_low_text_char_threshold", 100))
    fix_hyphens = bool(getattr(settings, "ingest_fix_hyphenation", False))

    loader = PyPDFLoader(str(file_path))
    pages = loader.load()
    cleaned: list[LCDocument] = []
    for page in pages:
        page.page_content = clean_text(page.page_content, fix_hyphens=fix_hyphens)
        if page.page_content:
            cleaned.append(page)

    if strip_headers and cleaned:
        cleaned, removed = strip_repeated_headers_footers(cleaned)
        cleaned = [p for p in cleaned if (p.page_content or "").strip()]
        if removed:
            for p in cleaned:
                p.metadata["stripped_headers"] = list(removed)[:10]

    if flag_low_text and cleaned:
        flagged = flag_low_text_pages(cleaned, char_threshold=low_text_threshold)
        for p in cleaned:
            if flagged:
                p.metadata["low_text_pages_doc"] = flagged

    logger.info(
        "pdf_loaded",
        path=str(file_path),
        pages=len(cleaned),
        strip_headers=strip_headers,
        flag_low_text=flag_low_text,
    )
    return cleaned


def split_documents(
    documents: list[LCDocument],
    document_id: str,
    filename: str,
    *,
    file_type: str = "pdf",
    extraction_method: str = "text",
    uploaded_at: str | None = None,
) -> list[LCDocument]:
    """
    Split documents into chunks with rich metadata:
    document_id, filename, file_type, location_type, location, chunk_id,
    parent_chunk_id, extraction_method, upload timestamp.
    """
    settings = get_settings()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        length_function=len,
        separators=["\n\n", "\n", ". ", " ", ""],
    )
    chunks = splitter.split_documents(documents)
    enriched: list[LCDocument] = []
    for idx, chunk in enumerate(chunks):
        # Prefer explicit section location (DOCX); else PDF 0-indexed page
        loc_type = str(chunk.metadata.get("location_type") or "")
        location = str(chunk.metadata.get("location") or "")
        page = chunk.metadata.get("page", 0)
        page_number = int(page) + 1 if isinstance(page, int) else int(chunk.metadata.get("page_number") or 1)
        if not loc_type:
            loc_type = "page"
        if not location:
            location = str(page_number)
        chunk_id = f"{document_id}_{idx}"
        parent = chunk.metadata.get("parent_chunk_id")
        meta: dict[str, Any] = {
            **chunk.metadata,
            "document_id": document_id,
            "filename": filename,
            "file_type": file_type or chunk.metadata.get("file_type") or "pdf",
            "location_type": loc_type,
            "location": location,
            "page_number": page_number,
            "chunk_id": chunk_id,
            "parent_chunk_id": parent,
            "extraction_method": extraction_method
            or chunk.metadata.get("extraction_method")
            or "text",
            "uploaded_at": uploaded_at or chunk.metadata.get("uploaded_at"),
            "chunk_index": idx,
            "token_count": count_tokens(chunk.page_content),
        }
        enriched.append(LCDocument(page_content=chunk.page_content, metadata=meta))
    logger.info("documents_chunked", document_id=document_id, chunks=len(enriched))
    return enriched
