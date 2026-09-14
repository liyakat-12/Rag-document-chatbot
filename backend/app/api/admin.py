"""Admin dashboard and health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.db.session import get_db
from backend.app.models.schemas import AdminStats, DocumentStats, HealthResponse, SystemInfo
from backend.app.services import chat_service

APP_VERSION = "1.1.0"

router = APIRouter(tags=["admin"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=APP_VERSION,
        llm_provider=settings.llm_provider,
        embedding_provider=settings.embedding_provider,
        retrieval_strategy="hybrid_rrf",
    )


@router.get("/admin/stats", response_model=AdminStats)
async def admin_dashboard(db: AsyncSession = Depends(get_db)) -> AdminStats:
    data = await chat_service.admin_stats(db)
    return AdminStats(
        documents=DocumentStats(**data["documents"]),
        total_sessions=data["total_sessions"],
        total_messages=data["total_messages"],
        total_tokens_used=data["total_tokens_used"],
        cache_hits=data["cache_hits"],
        cache_misses=data["cache_misses"],
        questions_answered=data.get("questions_answered", 0),
        feedback_up=data.get("feedback_up", 0),
        feedback_down=data.get("feedback_down", 0),
    )


@router.get("/admin/system", response_model=SystemInfo)
async def system_info() -> SystemInfo:
    """Read-only runtime configuration (never includes secrets)."""
    settings = get_settings()
    return SystemInfo(
        app=settings.app_name,
        version=APP_VERSION,
        llm_provider=settings.llm_provider,
        embedding_provider=settings.embedding_provider,
        local_embedding_model=settings.local_embedding_model,
        openai_chat_model=settings.openai_chat_model,
        llm_temperature=settings.llm_temperature,
        retrieval_strategy="hybrid_rrf",
        retriever_top_k=settings.retriever_top_k,
        hybrid_search_weight=settings.hybrid_search_weight,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        semantic_cache_enabled=settings.semantic_cache_enabled,
        semantic_cache_threshold=settings.semantic_cache_threshold,
        max_upload_size_mb=settings.max_upload_size_mb,
        app_env=settings.app_env,
    )
