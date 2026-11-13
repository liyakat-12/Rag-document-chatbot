"""Application configuration loaded from environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Central settings for the RAG Document Chatbot."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Application
    app_name: str = "DocuMind AI"
    app_env: Literal["development", "staging", "production"] = "development"
    debug: bool = True
    log_level: str = "INFO"
    secret_key: str = Field(default="change-me-to-a-long-random-string")

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://localhost:3000,http://localhost:8501"

    # LLM Provider
    llm_provider: Literal["openai", "azure_openai", "anthropic", "extractive"] = "openai"
    # Embeddings: openai uses paid API; local uses free FastEmbed (no quota)
    embedding_provider: Literal["openai", "local"] = "local"
    local_embedding_model: str = "BAAI/bge-small-en-v1.5"
    openai_api_key: str = ""
    openai_api_base: str = "https://api.openai.com/v1"
    openai_chat_model: str = "gpt-4o-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    # Low temperature preferred for factual document QA
    llm_temperature: float = 0.1

    azure_openai_api_key: str = ""
    azure_openai_endpoint: str = ""
    azure_openai_api_version: str = "2024-02-15-preview"
    azure_openai_chat_deployment: str = ""
    azure_openai_embedding_deployment: str = ""

    anthropic_api_key: str = ""
    anthropic_chat_model: str = "claude-3-5-sonnet-20241022"

    # Storage
    upload_dir: str = "uploads"
    vector_store_dir: str = "vector_store"
    max_upload_size_mb: int = 40
    allowed_extensions: str = ".pdf"

    # RAG
    chunk_size: int = 1000
    chunk_overlap: int = 200
    retriever_top_k: int = 4
    hybrid_search_weight: float = 0.5
    semantic_cache_enabled: bool = True
    semantic_cache_threshold: float = 0.95
    # Similarity scan embeds every miss — off by default for snappy exact-hash cache
    semantic_cache_similarity: bool = False
    # 384 for BAAI/bge-small-en-v1.5 (local); 1536 for text-embedding-3-small
    embedding_dimensions: int = 384
    token_budget_per_request: int = 8000

    # Refusal engine (Phase 2) — OFF by default; thresholds UNCALIBRATED
    refusal_enabled: bool = False
    refusal_min_rank_agreement: float = 0.25  # UNCALIBRATED
    refusal_min_faiss_similarity: float = 0.35  # UNCALIBRATED
    refusal_min_bm25_score: float = 1.0  # UNCALIBRATED
    refusal_min_content_term_coverage: float = 0.30  # UNCALIBRATED
    refusal_min_critical_term_coverage: float = 0.40  # UNCALIBRATED
    refusal_coverage_top_n: int = 4  # UNCALIBRATED
    refusal_not_found_hard_fails: int = 3  # UNCALIBRATED
    refusal_weak_evidence_soft_fails: int = 2  # UNCALIBRATED

    # Retrieval extras (Phase 3) — OFF / current behaviour by default
    retrieval_bm25_tokenizer: Literal["whitespace", "normalized"] = "whitespace"
    retrieval_reranker_enabled: bool = False
    retrieval_reranker_top_n: int = 16
    retrieval_reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    retrieval_exact_match_boost: bool = False
    retrieval_dedupe_near_duplicates: bool = False

    # Citation validation (Phase 4) — OFF by default
    citations_validate: bool = False

    # Ingestion quality (Phase 3 candidates) — OFF by default; change index hash when on
    ingest_strip_repeated_headers_footers: bool = False
    ingest_flag_low_text_pages: bool = False
    ingest_low_text_char_threshold: int = 100

    # Conversational follow-ups — OFF by default (keeps snapshot / expand_followup_query path)
    chat_rewrite_followups: bool = False

    # Prompt-injection guard — on for LLM providers only; extractive unaffected
    llm_injection_guard: bool = True

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/chatbot.db"

    @field_validator("cors_origins", mode="before")
    @classmethod
    def strip_origins(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def allowed_extension_list(self) -> list[str]:
        return [e.strip().lower() for e in self.allowed_extensions.split(",") if e.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_size_mb * 1024 * 1024

    @property
    def upload_path(self) -> Path:
        path = Path(self.upload_dir)
        if not path.is_absolute():
            path = BASE_DIR / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def vector_store_path(self) -> Path:
        path = Path(self.vector_store_dir)
        if not path.is_absolute():
            path = BASE_DIR / path
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def data_path(self) -> Path:
        path = BASE_DIR / "data"
        path.mkdir(parents=True, exist_ok=True)
        return path


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    settings = Settings()
    settings.upload_path
    settings.vector_store_path
    settings.data_path
    return settings
