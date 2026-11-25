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


def _retrieval_strategy(settings) -> str:
    strategy = "multi_query_hybrid_rrf" if settings.retrieval_multi_query_enabled else "hybrid_rrf"
    if settings.retrieval_reranker_enabled:
        strategy += "+cross_encoder_rerank"
    return strategy


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        version=APP_VERSION,
        llm_provider=settings.llm_provider,
        embedding_provider=settings.embedding_provider,
        retrieval_strategy=_retrieval_strategy(settings),
        ready=True,
    )


@router.get("/ready")
async def ready() -> dict:
    """Readiness: DB + vector store reachable (does not warm embeddings)."""
    from sqlalchemy import text

    from backend.app.db.session import AsyncSessionLocal
    from backend.app.rag.vector_store import get_vector_store

    checks: dict[str, str] = {}
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
    ok = all(v.startswith("ok") for v in checks.values())
    return {"ready": ok, "checks": checks}


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
        retrieval_strategy=_retrieval_strategy(settings),
        retriever_top_k=settings.retriever_top_k,
        hybrid_search_weight=settings.hybrid_search_weight,
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        semantic_cache_enabled=settings.semantic_cache_enabled,
        semantic_cache_threshold=settings.semantic_cache_threshold,
        max_upload_size_mb=settings.max_upload_size_mb,
        app_env=settings.app_env,
        retrieval_multi_query_enabled=settings.retrieval_multi_query_enabled,
        retrieval_multi_query_max_variants=settings.retrieval_multi_query_max_variants,
        retrieval_multi_query_candidate_multiplier=settings.retrieval_multi_query_candidate_multiplier,
        retrieval_reranker_enabled=settings.retrieval_reranker_enabled,
        retrieval_reranker_top_n=settings.retrieval_reranker_top_n,
        retrieval_reranker_model=settings.retrieval_reranker_model,
    )
