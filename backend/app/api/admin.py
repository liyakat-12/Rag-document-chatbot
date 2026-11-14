"""Admin dashboard and health endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import get_settings
from backend.app.db.session import get_db
from backend.app.models.schemas import AdminStats, DocumentStats, HealthResponse, SystemInfo
from backend.app.services import chat_service

APP_VERSION = "1.2.0"

router = APIRouter(tags=["admin"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    from backend.app.runtime_state import RUNTIME

    settings = get_settings()
    status = RUNTIME.status
    # Map runtime → health status field
    if status == "ready":
        health_status = "ok"
    elif status == "starting":
        health_status = "starting"
    else:
        health_status = "degraded"
    return HealthResponse(
        status=health_status,
        app=settings.app_name,
        version=APP_VERSION,
        llm_provider=settings.llm_provider,
        embedding_provider=settings.embedding_provider,
        retrieval_strategy="hybrid_rrf",
        ready=bool(RUNTIME.ready),
        detail=RUNTIME.detail or "",
    )


@router.get("/ready")
async def ready() -> dict:
    """Readiness: warmup complete + DB + vector store reachable."""
    from sqlalchemy import text

    from backend.app.db.session import AsyncSessionLocal
    from backend.app.rag.vector_store import get_vector_store
    from backend.app.runtime_state import RUNTIME

    checks: dict[str, str] = {"runtime": RUNTIME.status}
    try:
        async with AsyncSessionLocal() as db:
            await db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:
        checks["database"] = f"error: {exc}"
    try:
        store = get_vector_store()
        n = len(getattr(store.docstore, "_dict", {}) or {})
        checks["vector_store"] = f"ok ({n} chunks)"
    except Exception as exc:
        checks["vector_store"] = f"error: {exc}"
    ok = bool(RUNTIME.ready) and all(
        v.startswith("ok") or v == "ready" for k, v in checks.items() if k != "runtime"
    ) and RUNTIME.status == "ready"
    return {"ready": ok, "status": RUNTIME.status, "detail": RUNTIME.detail, "checks": checks}


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
        latency=data.get("latency") or {},
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
