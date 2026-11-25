"""Document API routes: upload, list, delete, reindex, stats, page viewer."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import Response
from openai import AuthenticationError, OpenAIError, RateLimitError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.db.session import get_db
from backend.app.models.schemas import (
    DocumentOut,
    DocumentPageMeta,
    DocumentStats,
    ReindexResponse,
    UploadResponse,
)
from backend.app.services import document_service
from backend.app.utils.security import validate_pdf_upload

router = APIRouter(prefix="/documents", tags=["documents"])

_PLACEHOLDER_KEYS = {
    "",
    "sk-your-openai-api-key-here",
    "change-me",
}


def _ensure_api_key_configured() -> None:
    """Only required when using paid OpenAI embeddings."""
    settings = get_settings()
    if settings.embedding_provider != "openai":
        return
    key = (settings.openai_api_key or "").strip()
    if key in _PLACEHOLDER_KEYS or key.startswith("sk-your-"):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "OpenAI API key is missing or still a placeholder. "
                "Set OPENAI_API_KEY in .env, or set EMBEDDING_PROVIDER=local "
                "to use free offline embeddings."
            ),
        )


@router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_documents(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    """Upload one or more PDF documents and index them."""
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    _ensure_api_key_configured()
    settings = get_settings()
    documents = []
    all_stages: list = []
    try:
        for file in files:
            raw = await validate_pdf_upload(file)
            doc, stages = await document_service.save_and_index_pdf(
                db, raw, file.filename or "document.pdf", settings.upload_path
            )
            documents.append(DocumentOut.model_validate(doc))
            all_stages.extend(stages)
    except AuthenticationError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "OpenAI rejected the API key (401). "
                "Update OPENAI_API_KEY in .env, or set EMBEDDING_PROVIDER=local."
            ),
        ) from exc
    except RateLimitError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=(
                "OpenAI quota exceeded (insufficient credits/billing). "
                "Add billing at https://platform.openai.com/account/billing "
                "OR set EMBEDDING_PROVIDER=local and LLM_PROVIDER=extractive in .env, "
                "then restart the backend."
            ),
        ) from exc
    except OpenAIError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"OpenAI API error while embedding document: {exc}",
        ) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to index document: {exc}",
        ) from exc

    return UploadResponse(
        message=f"Successfully uploaded and indexed {len(documents)} document(s).",
        documents=documents,
        stages=all_stages,
    )


# Alias matching required POST /upload
upload_router = APIRouter(tags=["documents"])


@upload_router.post("/upload", response_model=UploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_alias(
    files: list[UploadFile] = File(...),
    db: AsyncSession = Depends(get_db),
) -> UploadResponse:
    return await upload_documents(files=files, db=db)


@router.get("", response_model=list[DocumentOut])
async def get_documents(db: AsyncSession = Depends(get_db)) -> list[DocumentOut]:
    docs = await document_service.list_documents(db)
    return [DocumentOut.model_validate(d) for d in docs]


@router.delete("/{document_id}", status_code=status.HTTP_200_OK)
async def remove_document(document_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    ok = await document_service.delete_document(db, document_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"message": "Document deleted.", "id": document_id}


@router.post("/reindex", response_model=ReindexResponse)
async def reindex(db: AsyncSession = Depends(get_db)) -> ReindexResponse:
    docs, chunks = await document_service.reindex_all(db)
    return ReindexResponse(
        message="Reindex complete.",
        documents_reindexed=docs,
        chunks_indexed=chunks,
    )


@router.get("/stats", response_model=DocumentStats)
async def stats(db: AsyncSession = Depends(get_db)) -> DocumentStats:
    data = await document_service.document_stats(db)
    return DocumentStats(**data)


@router.get("/{document_id}/meta", response_model=DocumentPageMeta)
async def document_meta(document_id: str, db: AsyncSession = Depends(get_db)) -> DocumentPageMeta:
    """Document metadata for the Documents page viewer."""
    doc = await document_service.get_document(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    low_text = []
    extra = getattr(doc, "error_message", None)
    # low_text_pages stored as JSON in error_message prefix is avoided —
    # read optional sidecar metadata file written at ingest when flag is on.
    meta_path = Path(doc.file_path).with_suffix(Path(doc.file_path).suffix + ".meta.json")
    if meta_path.is_file():
        import json

        try:
            payload = json.loads(meta_path.read_text(encoding="utf-8"))
            low_text = list(payload.get("low_text_pages") or [])
        except Exception:
            low_text = []
    return DocumentPageMeta(
        id=doc.id,
        original_filename=doc.original_filename,
        page_count=doc.page_count,
        chunk_count=doc.chunk_count,
        file_size=doc.file_size,
        status=doc.status,
        error_message=doc.error_message,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
        low_text_pages=low_text,
    )


@router.get("/{document_id}/pages/{page_number}")
async def document_page_image(
    document_id: str,
    page_number: int,
    span: str = Query(default="", max_length=4000),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """Render a PDF page as PNG with optional citation span highlight."""
    from backend.app.rag.page_viewer import render_page_with_highlight

    doc = await document_service.get_document(db, document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found.")
    path = Path(doc.file_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="PDF file missing on disk.")
    if page_number < 1:
        raise HTTPException(status_code=400, detail="page_number must be >= 1")
    try:
        result = render_page_with_highlight(
            path,
            page_number,
            span=span,
            filename=doc.original_filename,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to render page: {exc}",
        ) from exc

    headers = {
        "X-Match-Mode": result.match_mode,
        "X-Page-Count": str(result.page_count),
        "X-Page-Number": str(result.page_number),
        "X-Cache-Hit": "1" if result.cache_hit else "0",
        "X-Filename": doc.original_filename,
    }
    if result.match_mode == "chunk_fallback" and span:
        headers["X-Chunk-Fallback"] = "1"
    return Response(content=result.png_bytes, media_type="image/png", headers=headers)
