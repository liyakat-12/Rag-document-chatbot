"""PDF page rendering with citation span highlighting (Phase 5).

Match order:
1. exact ``page.search_for``
2. whitespace / hyphenation-normalised match mapped back to page rects
3. best-matching text block (fuzzy token overlap)
4. caller falls back to chunk-text highlight (no page image rects)
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Optional

from backend.app.utils.logging import get_logger

logger = get_logger(__name__)

MatchMode = Literal["exact", "normalized", "block", "chunk_fallback"]

_WS_RE = re.compile(r"\s+")
_HYPHEN_BREAK_RE = re.compile(r"(\w)-\s+(\w)")


def normalize_match_text(text: str) -> str:
    """Collapse whitespace and join hyphenated line breaks for matching."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _HYPHEN_BREAK_RE.sub(r"\1\2", text)
    text = _WS_RE.sub(" ", text)
    return text.strip().lower()


def _token_overlap(a: str, b: str) -> float:
    ta = set(normalize_match_text(a).split())
    tb = set(normalize_match_text(b).split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


@dataclass
class HighlightResult:
    match_mode: MatchMode
    rects: list[tuple[float, float, float, float]]  # x0,y0,x1,y1 in page coords
    matched_text: str = ""
    block_text: str = ""
    page_text: str = ""


def find_highlight_rects(page: Any, span: str) -> HighlightResult:
    """Locate highlight rectangles for ``span`` on an open PyMuPDF page."""
    import fitz

    raw_span = (span or "").strip()
    page_text = page.get_text("text") or ""
    if not raw_span:
        return HighlightResult(
            match_mode="chunk_fallback",
            rects=[],
            page_text=page_text,
        )

    # 1) Exact search
    hits = page.search_for(raw_span, quads=False)
    if hits:
        rects = [(r.x0, r.y0, r.x1, r.y1) for r in hits]
        return HighlightResult(
            match_mode="exact",
            rects=rects,
            matched_text=raw_span,
            page_text=page_text,
        )

    # Also try first ~120 chars (long spans may fail exact search)
    short = raw_span[:120].strip()
    if len(short) >= 12 and short != raw_span:
        hits = page.search_for(short, quads=False)
        if hits:
            rects = [(r.x0, r.y0, r.x1, r.y1) for r in hits]
            return HighlightResult(
                match_mode="exact",
                rects=rects,
                matched_text=short,
                page_text=page_text,
            )

    # 2) Normalised: rebuild contiguous page string with char→bbox map
    norm_span = normalize_match_text(raw_span)
    if len(norm_span) >= 8:
        rects = _normalized_search(page, norm_span)
        if rects:
            return HighlightResult(
                match_mode="normalized",
                rects=rects,
                matched_text=norm_span,
                page_text=page_text,
            )

    # 3) Best-matching text block
    blocks = page.get_text("blocks") or []
    best_score = 0.0
    best_rect: tuple[float, float, float, float] | None = None
    best_text = ""
    for block in blocks:
        if len(block) < 5:
            continue
        btext = str(block[4] or "")
        if not btext.strip():
            continue
        score = _token_overlap(raw_span, btext)
        # Prefer longer blocks slightly when scores tie
        score += min(len(btext), 200) / 10000.0
        if score > best_score:
            best_score = score
            best_rect = (float(block[0]), float(block[1]), float(block[2]), float(block[3]))
            best_text = btext

    if best_rect is not None and best_score >= 0.15:
        return HighlightResult(
            match_mode="block",
            rects=[best_rect],
            matched_text=raw_span,
            block_text=best_text,
            page_text=page_text,
        )

    return HighlightResult(
        match_mode="chunk_fallback",
        rects=[],
        matched_text=raw_span,
        page_text=page_text,
    )


def _normalized_search(page: Any, norm_span: str) -> list[tuple[float, float, float, float]]:
    """Map normalised needle onto page word boxes (handles line breaks / hyphens)."""
    words = page.get_text("words") or []  # x0,y0,x1,y1,word,block,line,word_no
    if not words:
        return []

    lower_words = [str(w[4]).lower() for w in words]
    # Expand hyphenated pairs: "exam-" + "ple" → "example"
    expanded: list[tuple[str, list[int]]] = []
    i = 0
    while i < len(lower_words):
        tok = lower_words[i]
        idxs = [i]
        while tok.endswith("-") and i + 1 < len(lower_words):
            nxt = lower_words[i + 1]
            tok = tok[:-1] + nxt
            i += 1
            idxs.append(i)
        expanded.append((tok, idxs))
        i += 1

    hay = " ".join(t for t, _ in expanded)
    needle = norm_span
    pos = hay.find(needle)
    if pos < 0:
        hay_ns = hay.replace(" ", "")
        needle_ns = needle.replace(" ", "")
        if len(needle_ns) < 8:
            return []
        pos_ns = hay_ns.find(needle_ns)
        if pos_ns < 0:
            return []
        return _rects_for_ns_match(expanded, words, pos_ns, len(needle_ns))

    end = pos + len(needle)
    char_at = 0
    hit_word_idxs: list[int] = []
    for tok, idxs in expanded:
        start = char_at
        stop = char_at + len(tok)
        if stop > pos and start < end:
            hit_word_idxs.extend(idxs)
        char_at = stop + 1  # space
        if char_at - 1 >= end:
            break

    if not hit_word_idxs:
        return []
    rects = [
        (float(words[wi][0]), float(words[wi][1]), float(words[wi][2]), float(words[wi][3]))
        for wi in hit_word_idxs
    ]
    return _merge_nearby_rects(rects)


def _rects_for_ns_match(
    expanded: list[tuple[str, list[int]]],
    words: list,
    pos_ns: int,
    length_ns: int,
) -> list[tuple[float, float, float, float]]:
    cursor = 0
    hit: list[int] = []
    end = pos_ns + length_ns
    for tok, idxs in expanded:
        ns = tok.replace(" ", "")
        start = cursor
        stop = cursor + len(ns)
        if stop > pos_ns and start < end:
            hit.extend(idxs)
        cursor = stop
        if cursor >= end:
            break
    if not hit:
        return []
    rects = [(float(words[i][0]), float(words[i][1]), float(words[i][2]), float(words[i][3])) for i in hit]
    return _merge_nearby_rects(rects)


def _merge_nearby_rects(
    rects: list[tuple[float, float, float, float]],
    y_tol: float = 3.0,
) -> list[tuple[float, float, float, float]]:
    if not rects:
        return []
    # Group by approximate line (y0)
    sorted_r = sorted(rects, key=lambda r: (round(r[1] / y_tol), r[0]))
    lines: list[list[tuple[float, float, float, float]]] = []
    for r in sorted_r:
        if not lines:
            lines.append([r])
            continue
        prev = lines[-1][-1]
        if abs(r[1] - prev[1]) <= y_tol:
            lines[-1].append(r)
        else:
            lines.append([r])
    merged = []
    for line in lines:
        x0 = min(r[0] for r in line)
        y0 = min(r[1] for r in line)
        x1 = max(r[2] for r in line)
        y1 = max(r[3] for r in line)
        merged.append((x0, y0, x1, y1))
    return merged


@dataclass
class PageRenderResult:
    png_bytes: bytes
    match_mode: MatchMode
    page_number: int
    page_count: int
    width: int
    height: int
    highlight: HighlightResult
    cache_hit: bool = False
    filename: str = ""


def _cache_key(pdf_path: Path, page_number: int, span: str, dpi: int) -> str:
    st = pdf_path.stat()
    payload = f"{pdf_path.resolve()}|{st.st_mtime_ns}|{st.st_size}|{page_number}|{span}|{dpi}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:40]


def page_cache_dir() -> Path:
    from backend.app.config import get_settings

    path = get_settings().data_path / "page_cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def render_page_with_highlight(
    pdf_path: Path | str,
    page_number: int,
    span: str = "",
    *,
    dpi: int = 144,
    cache: bool = True,
    filename: str = "",
) -> PageRenderResult:
    """Render a 1-indexed PDF page to PNG, optionally highlighting ``span``."""
    import fitz

    path = Path(pdf_path)
    if not path.is_file():
        raise FileNotFoundError(f"PDF not found: {path}")

    span = span or ""
    key = _cache_key(path, page_number, span, dpi)
    cache_path = page_cache_dir() / f"{key}.png"
    meta_path = page_cache_dir() / f"{key}.json"

    if cache and cache_path.is_file() and meta_path.is_file():
        import json

        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        hl = HighlightResult(
            match_mode=meta.get("match_mode", "exact"),
            rects=[tuple(r) for r in meta.get("rects", [])],
            matched_text=meta.get("matched_text", ""),
            block_text=meta.get("block_text", ""),
            page_text=meta.get("page_text", ""),
        )
        return PageRenderResult(
            png_bytes=cache_path.read_bytes(),
            match_mode=hl.match_mode,
            page_number=page_number,
            page_count=int(meta.get("page_count", 0)),
            width=int(meta.get("width", 0)),
            height=int(meta.get("height", 0)),
            highlight=hl,
            cache_hit=True,
            filename=filename or path.name,
        )

    doc = fitz.open(path)
    try:
        page_count = doc.page_count
        idx = max(0, min(page_number - 1, page_count - 1))
        page = doc.load_page(idx)
        hl = find_highlight_rects(page, span) if span else HighlightResult(
            match_mode="chunk_fallback",
            rects=[],
            page_text=page.get_text("text") or "",
        )

        # Draw highlights on a copy via annot-free rectangle overlays on pixmap
        # Use Shape drawing on a display list clone — simplest: draw quads then render
        if hl.rects:
            shape = page.new_shape()
            for x0, y0, x1, y1 in hl.rects:
                shape.draw_rect(fitz.Rect(x0, y0, x1, y1))
            shape.finish(
                color=(0.06, 0.46, 0.43),  # teal outline
                fill=(0.8, 0.98, 0.94),
                fill_opacity=0.35,
                width=0.8,
            )
            shape.commit()

        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        png = pix.tobytes("png")
        result = PageRenderResult(
            png_bytes=png,
            match_mode=hl.match_mode,
            page_number=idx + 1,
            page_count=page_count,
            width=pix.width,
            height=pix.height,
            highlight=hl,
            cache_hit=False,
            filename=filename or path.name,
        )
    finally:
        doc.close()

    if cache:
        import json

        cache_path.write_bytes(result.png_bytes)
        meta_path.write_text(
            json.dumps(
                {
                    "match_mode": result.match_mode,
                    "rects": result.highlight.rects,
                    "matched_text": result.highlight.matched_text,
                    "block_text": result.highlight.block_text,
                    "page_text": (result.highlight.page_text or "")[:2000],
                    "page_count": result.page_count,
                    "width": result.width,
                    "height": result.height,
                }
            ),
            encoding="utf-8",
        )

    return result


def highlight_span_in_text(chunk_text: str, span: str) -> str:
    """Fallback: return chunk text with ``>>>span<<<`` markers (UI can style)."""
    text = chunk_text or ""
    needle = (span or "").strip()
    if not needle:
        return text
    idx = text.lower().find(needle.lower())
    if idx >= 0:
        end = idx + len(needle)
        return text[:idx] + ">>>" + text[idx:end] + "<<<" + text[end:]
    # Normalised search in chunk
    norm_text = normalize_match_text(text)
    norm_span = normalize_match_text(needle)
    pos = norm_text.find(norm_span)
    if pos >= 0:
        # Approximate: mark whole chunk as matched region
        return ">>>" + text + "<<<"
    return text
