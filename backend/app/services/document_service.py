"""Document upload, indexing, deletion, and reindex services."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any
from uuid import uuid4

from langchain_core.documents import Document as LCDocument
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.models import Document, DocumentChunk
from backend.app.rag.hybrid_search import rebuild_bm25_index
from backend.app.rag.ingest import load_pdf, split_documents
from backend.app.rag.vector_store import (
    add_documents,
    delete_document_vectors,
    rebuild_from_documents,
)
from backend.app.utils.logging import get_logger
from backend.app.utils.security import sanitize_filename
from backend.app.utils.text import clean_text

logger = get_logger(__name__)


def _stage(name: str, ok: bool, ms: float, detail: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "ok": ok,
        "ms": round(ms, 2),
        "detail": detail,
    }


async def save_and_index_pdf(
    session: AsyncSession,
    raw_bytes: bytes,
    original_filename: str,
    upload_dir: Path,
) -> tuple[Document, list[dict[str, Any]]]:
    """
    Persist a PDF to disk, parse, chunk, embed, and store in FAISS + BM25.

    Returns (document, pipeline_stages) where stages reflect work that actually ran.
    """
    stages: list[dict[str, Any]] = []
    t_all = time.perf_counter()

    safe_name = sanitize_filename(original_filename)
    doc_id = str(uuid4())
    stored_name = f"{doc_id}_{safe_name}"
    file_path = upload_dir / stored_name

    t0 = time.perf_counter()
    file_path.write_bytes(raw_bytes)
    stages.append(_stage("uploaded", True, (time.perf_counter() - t0) * 1000, f"{len(raw_bytes)} bytes"))

    document = Document(
        id=doc_id,
        filename=stored_name,
        original_filename=original_filename,
        file_path=str(file_path),
        file_size=len(raw_bytes),
        status="pending",
    )
    session.add(document)
    await session.flush()

    try:
        t0 = time.perf_counter()
        pages = load_pdf(file_path)
        if not pages:
            raise ValueError("PDF contains no extractable text pages.")
        document.page_count = len(pages)
        stages.append(
            _stage(
                "extracted",
                True,
                (time.perf_counter() - t0) * 1000,
                f"{len(pages)} page(s)",
            )
        )

        t0 = time.perf_counter()
        # clean_text runs inside split/load path; measure explicit clean of page text
        cleaned_chars = sum(len(clean_text(p.page_content or "")) for p in pages)
        stages.append(
            _stage(
                "cleaned",
                True,
                (time.perf_counter() - t0) * 1000,
                f"{cleaned_chars} characters",
            )
        )

        t0 = time.perf_counter()
        chunks = split_documents(pages, document_id=doc_id, filename=original_filename)
        if not chunks:
            raise ValueError("No text chunks could be created from this PDF.")
        stages.append(
            _stage("chunked", True, (time.perf_counter() - t0) * 1000, f"{len(chunks)} chunks")
        )

        chunk_rows: list[DocumentChunk] = []
        for chunk in chunks:
            chunk_rows.append(
                DocumentChunk(
                    id=chunk.metadata["chunk_id"],
                    document_id=doc_id,
                    chunk_index=int(chunk.metadata["chunk_index"]),
                    page_number=int(chunk.metadata["page_number"]),
                    content=chunk.page_content,
                    token_count=int(chunk.metadata.get("token_count", 0)),
                )
            )
        session.add_all(chunk_rows)

        t0 = time.perf_counter()
        faiss_ids = add_documents(chunks)
        for row, fid in zip(chunk_rows, faiss_ids):
            row.faiss_id = hash(fid) % (10**9)
        stages.append(
            _stage(
                "embedded_faiss",
                True,
                (time.perf_counter() - t0) * 1000,
                f"{len(faiss_ids)} vectors",
            )
        )

        t0 = time.perf_counter()
        rebuild_bm25_index()
        stages.append(_stage("bm25_updated", True, (time.perf_counter() - t0) * 1000))

        document.chunk_count = len(chunks)
        document.status = "indexed"
        total_ms = (time.perf_counter() - t_all) * 1000
        logger.info(
            "document_indexed",
            document_id=doc_id,
            pages=document.page_count,
            chunks=len(chunks),
            total_ms=round(total_ms, 2),
        )
    except Exception as exc:
        document.status = "error"
        document.error_message = str(exc)
        stages.append(_stage("failed", False, 0, str(exc)[:200]))
        logger.error("document_index_failed", document_id=doc_id, error=str(exc))
        raise

    await session.flush()
    await session.refresh(document)
    return document, stages


async def list_documents(session: AsyncSession) -> list[Document]:
    result = await session.execute(select(Document).order_by(Document.created_at.desc()))
    return list(result.scalars().all())


async def get_document(session: AsyncSession, document_id: str) -> Document | None:
    result = await session.execute(select(Document).where(Document.id == document_id))
    return result.scalar_one_or_none()


async def delete_document(session: AsyncSession, document_id: str) -> bool:
    document = await get_document(session, document_id)
    if not document:
        return False

    delete_document_vectors(document_id)
    path = Path(document.file_path)
    if path.exists():
        path.unlink(missing_ok=True)

    await session.delete(document)
    rebuild_bm25_index()
    logger.info("document_deleted", document_id=document_id)
    return True


async def reindex_all(session: AsyncSession) -> tuple[int, int]:
    """Re-parse all PDFs and rebuild FAISS + BM25. Returns (docs, chunks)."""
    result = await session.execute(
        select(Document).options(selectinload(Document.chunks)).order_by(Document.created_at)
    )
    documents = list(result.scalars().all())
    all_lc_docs: list[LCDocument] = []

    for document in documents:
        path = Path(document.file_path)
        if not path.exists():
            document.status = "error"
            document.error_message = "File missing on disk"
            continue
        try:
            for ch in list(document.chunks):
                await session.delete(ch)
            await session.flush()

            pages = load_pdf(path)
            document.page_count = len(pages)
            chunks = split_documents(
                pages, document_id=document.id, filename=document.original_filename
            )
            chunk_rows = []
            for chunk in chunks:
                chunk_rows.append(
                    DocumentChunk(
                        id=chunk.metadata["chunk_id"],
                        document_id=document.id,
                        chunk_index=int(chunk.metadata["chunk_index"]),
                        page_number=int(chunk.metadata["page_number"]),
                        content=chunk.page_content,
                        token_count=int(chunk.metadata.get("token_count", 0)),
                    )
                )
            session.add_all(chunk_rows)
            document.chunk_count = len(chunks)
            document.status = "indexed"
            document.error_message = None
            all_lc_docs.extend(chunks)
        except Exception as exc:
            document.status = "error"
            document.error_message = str(exc)
            logger.error("reindex_doc_failed", document_id=document.id, error=str(exc))

    total_chunks = rebuild_from_documents(all_lc_docs)
    rebuild_bm25_index()
    logger.info("reindex_complete", documents=len(documents), chunks=total_chunks)
    return len(documents), total_chunks


async def document_stats(session: AsyncSession) -> dict:
    total = await session.scalar(select(func.count()).select_from(Document)) or 0
    pages = await session.scalar(select(func.coalesce(func.sum(Document.page_count), 0))) or 0
    chunks = await session.scalar(select(func.coalesce(func.sum(Document.chunk_count), 0))) or 0
    size = await session.scalar(select(func.coalesce(func.sum(Document.file_size), 0))) or 0
    indexed = await session.scalar(
        select(func.count()).select_from(Document).where(Document.status == "indexed")
    ) or 0
    return {
        "total_documents": total,
        "total_pages": pages,
        "total_chunks": chunks,
        "total_size_bytes": size,
        "indexed_documents": indexed,
    }
