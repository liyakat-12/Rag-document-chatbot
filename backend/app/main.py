"""FastAPI application entrypoint."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.app.api.router import api_router
from backend.app.config import get_settings
from backend.app.db.session import init_db
from backend.app.runtime_state import RUNTIME, mark_degraded, mark_ready, mark_starting
from backend.app.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


def _warmup_sync() -> None:
    from backend.app.rag.hybrid_search import rebuild_bm25_index
    from backend.app.rag.llm_factory import get_shared_embeddings
    from backend.app.rag.vector_store import get_vector_store

    emb = get_shared_embeddings()
    emb.embed_query("warmup")
    get_vector_store()
    rebuild_bm25_index()


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        settings = get_settings()
    except RuntimeError as exc:
        logger.error("config_invalid", error=str(exc))
        mark_degraded("Configuration error", error=str(exc))
        app.state.config_error = str(exc)
        yield
        return

    logger.info("startup", app=settings.app_name, env=settings.app_env)
    mark_starting()
    await init_db()

    async def _warm() -> None:
        try:
            await asyncio.to_thread(_warmup_sync)
            mark_ready()
            logger.info(
                "warmup_complete",
                embedding_provider=settings.embedding_provider,
            )
        except Exception as exc:
            mark_degraded("Warmup incomplete — answering may be slow", error=str(exc))
            logger.warning("vector_store_warmup_skipped", error=str(exc))

    warm_task = asyncio.create_task(_warm())
    yield
    warm_task.cancel()
    try:
        await warm_task
    except asyncio.CancelledError:
        pass
    logger.info("shutdown")


def create_app() -> FastAPI:
    # Load settings early so invalid config fails with a clear message
    try:
        settings = get_settings()
        config_error: str | None = None
    except RuntimeError as exc:
        settings = None
        config_error = str(exc)

    app = FastAPI(
        title=(settings.app_name if settings else "DocuMind AI"),
        version="1.0.0",
        description=(
            "Production-ready RAG Document Chatbot with hybrid search, "
            "citations, and streaming."
        ),
        lifespan=lifespan,
    )
    app.state.config_error = config_error

    origins = (
        settings.cors_origin_list
        if settings
        else ["http://localhost:8501", "http://localhost:7860"]
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_request_id(request, call_next):
        import time
        import uuid

        if getattr(app.state, "config_error", None) and request.url.path.endswith("/health"):
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "app": "DocuMind AI",
                    "version": "1.0.0",
                    "llm_provider": "unknown",
                    "embedding_provider": "unknown",
                    "retrieval_strategy": "hybrid_rrf",
                    "ready": False,
                    "detail": app.state.config_error,
                },
            )

        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        t0 = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time-Ms"] = f"{elapsed_ms:.2f}"
        return response

    if settings is not None:
        app.include_router(api_router, prefix=settings.api_prefix)
        api_prefix = settings.api_prefix
    else:
        api_prefix = "/api/v1"

        @app.get(f"{api_prefix}/health")
        async def health_fallback():
            return JSONResponse(
                status_code=503,
                content={
                    "status": "error",
                    "app": "DocuMind AI",
                    "version": "1.0.0",
                    "ready": False,
                    "detail": config_error,
                },
            )

    @app.get("/")
    async def root():
        return {
            "app": settings.app_name if settings else "DocuMind AI",
            "docs": "/docs",
            "api": api_prefix,
            "health": f"{api_prefix}/health",
            "runtime": RUNTIME.status,
        }

    return app


app = create_app()
