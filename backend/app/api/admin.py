"""Admin dashboard and health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.db.session import get_db
from backend.app.models.schemas import AdminStats, DocumentStats, HealthResponse
from backend.app.services import chat_service

router = APIRouter(tags=["admin"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version="1.0.0",
        llm_provider=settings.llm_provider,
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
    )
