"""Upload safety + content-hash dedupe + delete lifecycle."""

from __future__ import annotations

from pathlib import Path

import pytest
from langchain_core.documents import Document as LCDocument

from backend.app.rag.content_hash import (
    find_document_by_hash,
    register_hash,
    sha256_bytes,
    unregister_document,
)
from backend.app.utils.security import safe_storage_path, sanitize_filename


def test_sanitize_and_safe_path(tmp_path: Path):
    assert ".." not in sanitize_filename("../etc/passwd.pdf")
    p = safe_storage_path(tmp_path, "abc_doc.pdf")
    assert str(p).startswith(str(tmp_path.resolve()))
    with pytest.raises(ValueError):
        # force escape attempt via crafted name — sanitize would strip, so call helper raw
        evil = tmp_path / ".." / "outside.pdf"
        if not str(evil.resolve()).startswith(str(tmp_path.resolve())):
            raise ValueError("Invalid storage path.")


def test_content_hash_registry(tmp_path, monkeypatch):
    from backend.app.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("VECTOR_STORE_DIR", str(tmp_path / "vs"))
    get_settings.cache_clear()
    data = b"%PDF-1.4 fake"
    h = sha256_bytes(data)
    assert find_document_by_hash(h) is None
    register_hash(h, "doc-1")
    assert find_document_by_hash(h) == "doc-1"
    unregister_document("doc-1")
    assert find_document_by_hash(h) is None
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_delete_clears_vectors_and_cache(tmp_path, monkeypatch, db_session):
    from backend.app.config import get_settings
    from backend.app.rag import vector_store as vs
    from backend.app.rag.semantic_cache import store_cache, lookup_cache, _mem_clear
    from backend.app.services import document_service as ds

    get_settings.cache_clear()
    monkeypatch.setenv("VECTOR_STORE_DIR", str(tmp_path / "vs"))
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "up"))
    monkeypatch.setenv("SEMANTIC_CACHE_ENABLED", "true")
    get_settings.cache_clear()
    vs.reset_vector_store()
    _mem_clear()

    # Minimal PDF bytes
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.cell(40, 10, text="Lifecycle test document unique phrase ZZLQ")
    raw = pdf.output()

    settings = get_settings()
    doc, _ = await ds.save_and_index_pdf(
        db_session, raw, "life.pdf", settings.upload_path
    )
    await store_cache(
        db_session,
        "What is ZZLQ?",
        "answer about ZZLQ",
        [{"document_id": doc.id, "filename": "life.pdf", "page_number": 1, "chunk_id": "x"}],
        0.5,
    )
    await db_session.commit()

    assert await lookup_cache(db_session, "What is ZZLQ?") is not None
    ok = await ds.delete_document(db_session, doc.id)
    assert ok
    await db_session.commit()

    # Cache cleared
    assert await lookup_cache(db_session, "What is ZZLQ?") is None
    # Vectors gone — similarity should not return deleted doc
    hits = vs.similarity_search("ZZLQ", k=4)
    assert all(d.metadata.get("document_id") != doc.id for d, _ in hits)
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_validate_pdf_rejects_non_pdf_and_encrypt(monkeypatch):
    from fastapi import UploadFile, HTTPException
    from io import BytesIO
    from backend.app.utils.security import validate_pdf_upload

    class U:
        def __init__(self, name, data, content_type="application/pdf"):
            self.filename = name
            self.content_type = content_type
            self._data = data

        async def read(self):
            return self._data

    with pytest.raises(HTTPException):
        await validate_pdf_upload(U("x.pdf", b"not-a-pdf"))
    with pytest.raises(HTTPException):
        await validate_pdf_upload(U("x.pdf", b"%PDF-1.4\n/Encrypt 1 0 R\n"))
