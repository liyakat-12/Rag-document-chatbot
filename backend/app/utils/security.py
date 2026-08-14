"""File validation and sanitization utilities."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from backend.app.config import get_settings


def sanitize_filename(filename: str) -> str:
    """Sanitize an uploaded filename to prevent path traversal and unsafe chars."""
    name = Path(filename).name
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = re.sub(r"[^\w.\- ]+", "", name).strip()
    name = re.sub(r"\s+", "_", name)
    if not name or name in {".", ".."}:
        name = "document.pdf"
    if not name.lower().endswith(".pdf"):
        name = f"{name}.pdf"
    # Limit length
    if len(name) > 200:
        stem = Path(name).stem[:190]
        name = f"{stem}.pdf"
    return name


async def validate_pdf_upload(file: UploadFile) -> bytes:
    """
    Validate that an upload is a PDF within size limits.
    Returns the raw file bytes.
    """
    settings = get_settings()

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing filename.",
        )

    ext = Path(file.filename).suffix.lower()
    if ext not in settings.allowed_extension_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Only PDF files are allowed. Got: {ext or 'unknown'}",
        )

    content_type = (file.content_type or "").lower()
    if content_type and content_type not in {
        "application/pdf",
        "application/x-pdf",
        "binary/octet-stream",
        "application/octet-stream",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid content type: {content_type}. Expected application/pdf.",
        )

    data = await file.read()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file.",
        )

    if len(data) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_upload_size_mb} MB.",
        )

    # Magic-byte check for PDF
    if not data.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File content is not a valid PDF.",
        )

    return data
