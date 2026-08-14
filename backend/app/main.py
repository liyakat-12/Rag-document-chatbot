"""FastAPI application entrypoint."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.api.router import api_router
from backend.app.config import get_settings
from backend.app.db.session import init_db
from backend.app.utils.logging import get_logger, setup_logging

setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    logger.info("startup", app=settings.app_name, env=settings.app_env)
    await init_db()
    # Warm vector store + BM25 if index exists
    try:
        from backend.app.rag.hybrid_search import rebuild_bm25_index
        from backend.app.rag.vector_store import get_vector_store

        get_vector_store()
        rebuild_bm25_index()
    except Exception as exc:
        logger.warning("vector_store_warmup_skipped", error=str(exc))
    yield
    logger.info("shutdown")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="1.0.0",
        description="Production-ready RAG Document Chatbot with hybrid search, citations, and streaming.",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/")
    async def root():
        return {
            "app": settings.app_name,
            "docs": "/docs",
            "api": settings.api_prefix,
            "health": f"{settings.api_prefix}/health",
        }

    return app


app = create_app()
