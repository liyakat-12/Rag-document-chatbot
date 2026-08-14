"""PDF loading, cleaning, and chunking."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document as LCDocument
from langchain_text_splitters import RecursiveCharacterTextSplitter

from backend.app.config import get_settings
from backend.app.utils.logging import get_logger
from backend.app.utils.text import clean_text
from backend.app.utils.tokens import count_tokens

logger = get_logger(__name__)


def load_pdf(file_path: Path) -> list[LCDocument]:
    """Load a PDF and return LangChain documents (one per page)."""
    loader = PyPDFLoader(str(file_path))
    pages = loader.load()
    cleaned: list[LCDocument] = []
    for page in pages:
        page.page_content = clean_text(page.page_content)
        if page.page_content:
            cleaned.append(page)
    logger.info("pdf_loaded", path=str(file_path), pages=len(cleaned))
    return cleaned


def split_documents(
    documents: list[LCDocument],
    document_id: str,
    filename: str,
) -> list[LCDocument]:
    """
    Split documents into chunks with rich metadata:
    filename, page_number, chunk_id, document_id.
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
        page = chunk.metadata.get("page", 0)
        # PyPDFLoader uses 0-indexed pages
        page_number = int(page) + 1 if isinstance(page, int) else 1
        chunk_id = f"{document_id}_{idx}"
        meta: dict[str, Any] = {
            **chunk.metadata,
            "document_id": document_id,
            "filename": filename,
            "page_number": page_number,
            "chunk_id": chunk_id,
            "chunk_index": idx,
            "token_count": count_tokens(chunk.page_content),
        }
        enriched.append(LCDocument(page_content=chunk.page_content, metadata=meta))
    logger.info("documents_chunked", document_id=document_id, chunks=len(enriched))
    return enriched
