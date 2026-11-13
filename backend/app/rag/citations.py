"""Citation validation against the evidence set (flagged off by default)."""

from __future__ import annotations

from typing import Any

from langchain_core.documents import Document as LCDocument

from backend.app.utils.logging import get_logger

logger = get_logger(__name__)


def validate_citations(
    citations: list[dict[str, Any]],
    evidence: list[tuple[LCDocument, float]],
    *,
    request_id: str = "",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Keep only citations that map to a chunk in this answer's evidence set.

    Match on document_id, filename, and page_number (and chunk_id when present).
    """
    allowed: set[tuple[str, str, int, str]] = set()
    for doc, _ in evidence:
        meta = doc.metadata or {}
        allowed.add(
            (
                str(meta.get("document_id") or ""),
                str(meta.get("filename") or ""),
                int(meta.get("page_number") or 0),
                str(meta.get("chunk_id") or ""),
            )
        )
    # Also allow match without chunk_id (filename+page+doc)
    allowed_loose = {(d, f, p) for d, f, p, _ in allowed}

    valid: list[dict[str, Any]] = []
    dropped = 0
    for c in citations:
        key = (
            str(c.get("document_id") or ""),
            str(c.get("filename") or ""),
            int(c.get("page_number") or 0),
            str(c.get("chunk_id") or ""),
        )
        loose = (key[0], key[1], key[2])
        ok = key in allowed or (key[3] == "" and loose in allowed_loose)
        if not ok and key[3]:
            # chunk_id present but mismatched — reject
            ok = False
        if not ok:
            # Accept if chunk_id alone matches evidence
            ok = any(key[3] and key[3] == a[3] for a in allowed)
        if ok:
            valid.append(c)
        else:
            dropped += 1
            logger.warning(
                "citation_dropped",
                request_id=request_id,
                filename=c.get("filename"),
                page=c.get("page_number"),
                chunk_id=c.get("chunk_id"),
            )

    total = len(citations) or 1
    stats = {
        "input": len(citations),
        "valid": len(valid),
        "dropped": dropped,
        "valid_share": round(len(valid) / total, 4),
        "request_id": request_id,
    }
    return valid, stats


def citation_precision(pred: list[dict[str, Any]], gold_filenames_pages: set[tuple[str, int]]) -> float | None:
    if not pred:
        return None
    hits = 0
    for c in pred:
        if (str(c.get("filename") or ""), int(c.get("page_number") or 0)) in gold_filenames_pages:
            hits += 1
    return hits / len(pred)


def citation_recall(pred: list[dict[str, Any]], gold_filenames_pages: set[tuple[str, int]]) -> float | None:
    if not gold_filenames_pages:
        return None
    pred_set = {
        (str(c.get("filename") or ""), int(c.get("page_number") or 0)) for c in pred
    }
    hits = len(pred_set & gold_filenames_pages)
    return hits / len(gold_filenames_pages)


def valid_citation_share(valid: int, total: int) -> float | None:
    if total <= 0:
        return None
    return valid / total
