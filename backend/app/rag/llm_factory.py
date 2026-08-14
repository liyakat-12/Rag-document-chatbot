"""LLM and embedding factory — provider-configurable."""

from __future__ import annotations

from functools import lru_cache

from langchain_anthropic import ChatAnthropic
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings, ChatOpenAI, OpenAIEmbeddings

from backend.app.config import Settings, get_settings
from backend.app.utils.logging import get_logger

logger = get_logger(__name__)


class ExtractiveChatModel(BaseChatModel):
    """
    Offline fallback LLM: returns the most relevant context snippets
    without calling an external API (useful when OpenAI quota is exhausted).
    """

    @property
    def _llm_type(self) -> str:
        return "extractive"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager=None,
        **kwargs,
    ) -> ChatResult:
        text = self._extract_answer(messages)
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=text))])

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager=None,
        **kwargs,
    ) -> ChatResult:
        return self._generate(messages, stop=stop, run_manager=run_manager, **kwargs)

    def _stream(self, messages, stop=None, run_manager=None, **kwargs):
        text = self._extract_answer(messages)
        step = max(24, len(text) // 20 or 1)
        for i in range(0, len(text), step):
            yield AIMessageChunk(content=text[i : i + step])

    async def _astream(self, messages, stop=None, run_manager=None, **kwargs):
        for chunk in self._stream(messages, stop=stop, run_manager=run_manager, **kwargs):
            yield chunk

    @staticmethod
    def _extract_answer(messages: list[BaseMessage]) -> str:
        from backend.app.rag.qa_chain import NOT_FOUND_MESSAGE

        human = ""
        for m in reversed(messages):
            if getattr(m, "type", None) == "human" or m.__class__.__name__ == "HumanMessage":
                human = str(m.content)
                break
        # Prompt contains Context: ... Question: ...
        if "Context:" in human and "Question:" in human:
            ctx = human.split("Context:", 1)[1]
            question_part = ctx.split("Question:", 1)
            context = question_part[0].strip()
            question = question_part[1].split("Answer:", 1)[0].strip() if len(question_part) > 1 else ""
        else:
            context = human
            question = ""

        if not context or context == "(none)" or "---" not in context and len(context) < 20:
            # Still try raw context
            if len(context.strip()) < 20:
                return NOT_FOUND_MESSAGE

        snippets = [s.strip() for s in context.split("---") if s.strip()]
        if not snippets:
            return NOT_FOUND_MESSAGE

        # Prefer snippets that share words with the question
        q_words = {w.lower() for w in question.split() if len(w) > 3}

        def score(s: str) -> int:
            words = {w.lower() for w in s.split() if len(w) > 3}
            return len(q_words & words)

        ranked = sorted(snippets, key=score, reverse=True)
        top = ranked[:2]
        body = "\n\n".join(top)
        # Trim overly long extractive answers
        if len(body) > 1800:
            body = body[:1800] + "…"
        header = (
            "Based on the uploaded documents (offline extractive mode — "
            "OpenAI quota unavailable):\n\n"
        )
        return header + body


def get_chat_llm(settings: Settings | None = None, streaming: bool = False) -> BaseChatModel:
    """Return a chat LLM based on configured provider."""
    settings = settings or get_settings()
    provider = settings.llm_provider

    if provider == "extractive":
        return ExtractiveChatModel()

    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return ChatOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            model=settings.openai_chat_model,
            temperature=0.0,
            streaming=streaming,
        )

    if provider == "azure_openai":
        if not settings.azure_openai_api_key or not settings.azure_openai_endpoint:
            raise ValueError("Azure OpenAI credentials are required when LLM_PROVIDER=azure_openai")
        return AzureChatOpenAI(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
            azure_deployment=settings.azure_openai_chat_deployment,
            temperature=0.0,
            streaming=streaming,
        )

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        return ChatAnthropic(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_chat_model,
            temperature=0.0,
            streaming=streaming,
        )

    raise ValueError(f"Unsupported LLM provider: {provider}")


def get_embeddings(settings: Settings | None = None) -> Embeddings:
    """Return an embeddings model based on configured provider."""
    settings = settings or get_settings()
    emb_provider = settings.embedding_provider

    if emb_provider == "local":
        try:
            from langchain_community.embeddings.fastembed import FastEmbedEmbeddings
        except ImportError as exc:
            raise ImportError(
                "Local embeddings require the 'fastembed' package. "
                "Install with: pip install fastembed"
            ) from exc
        logger.info("embeddings_local", model=settings.local_embedding_model)
        return FastEmbedEmbeddings(model_name=settings.local_embedding_model)

    if emb_provider == "openai" or settings.llm_provider in ("openai", "anthropic"):
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI embeddings")
        kwargs = {
            "api_key": settings.openai_api_key,
            "base_url": settings.openai_api_base,
            "model": settings.openai_embedding_model,
        }
        # dimensions only supported by some OpenAI embedding models
        if "text-embedding-3" in settings.openai_embedding_model:
            kwargs["dimensions"] = settings.embedding_dimensions
        return OpenAIEmbeddings(**kwargs)

    if settings.llm_provider == "azure_openai":
        return AzureOpenAIEmbeddings(
            api_key=settings.azure_openai_api_key,
            azure_endpoint=settings.azure_openai_endpoint,
            api_version=settings.azure_openai_api_version,
            azure_deployment=settings.azure_openai_embedding_deployment,
        )

    raise ValueError(f"Unsupported embeddings provider: {emb_provider}")


@lru_cache
def get_shared_embeddings() -> Embeddings:
    """Cached embeddings instance for reuse across requests."""
    return get_embeddings()
