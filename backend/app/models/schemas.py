"""Shared Pydantic schemas for API request/response models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RatingEnum(str, Enum):
    UP = "up"
    DOWN = "down"
    NONE = "none"


# ---------------------------------------------------------------------------
# Documents
# ---------------------------------------------------------------------------


class DocumentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    original_filename: str
    file_size: int
    page_count: int
    chunk_count: int
    status: str
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class DocumentStats(BaseModel):
    total_documents: int
    total_pages: int
    total_chunks: int
    total_size_bytes: int
    indexed_documents: int


class IngestStage(BaseModel):
    name: str
    ok: bool
    ms: float = 0.0
    detail: str = ""


class UploadResponse(BaseModel):
    message: str
    documents: list[DocumentOut]
    stages: list[IngestStage] = []


# ---------------------------------------------------------------------------
# Chat
# ---------------------------------------------------------------------------


class SourceCitation(BaseModel):
    document_id: str
    filename: str
    page_number: int
    chunk_id: str
    content: str
    score: float = 0.0


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    session_id: Optional[str] = None
    stream: bool = True
    document_ids: Optional[list[str]] = None  # metadata filtering


class ChatResponse(BaseModel):
    session_id: str
    message_id: str
    answer: str
    sources: list[SourceCitation]
    confidence: float
    retrieved_chunks: list[SourceCitation]
    tokens_used: int = 0
    cached: bool = False
    retrieval: dict[str, Any] = Field(default_factory=dict)
    timings: dict[str, Any] = Field(default_factory=dict)


class RateRequest(BaseModel):
    rating: RatingEnum


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: str
    content: str
    sources: Optional[list[dict[str, Any]]] = None
    confidence: Optional[float] = None
    rating: str = "none"
    tokens_used: int = 0
    created_at: datetime


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    summary: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class SessionDetail(SessionOut):
    messages: list[MessageOut] = []


class HistoryResponse(BaseModel):
    sessions: list[SessionOut]


class ReindexResponse(BaseModel):
    message: str
    documents_reindexed: int
    chunks_indexed: int


class AdminStats(BaseModel):
    documents: DocumentStats
    total_sessions: int
    total_messages: int
    total_tokens_used: int
    cache_hits: int
    cache_misses: int
    questions_answered: int = 0
    feedback_up: int = 0
    feedback_down: int = 0


class HealthResponse(BaseModel):
    status: str
    app: str
    version: str
    llm_provider: str
    embedding_provider: str = ""
    retrieval_strategy: str = "hybrid_rrf"


class SystemInfo(BaseModel):
    app: str
    version: str
    llm_provider: str
    embedding_provider: str
    local_embedding_model: str
    openai_chat_model: str
    llm_temperature: float = 0.1
    retrieval_strategy: str
    retriever_top_k: int
    hybrid_search_weight: float
    chunk_size: int
    chunk_overlap: int
    semantic_cache_enabled: bool
    semantic_cache_threshold: float
    max_upload_size_mb: int
    app_env: str
