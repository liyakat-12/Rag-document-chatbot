"""LLM and embedding factory — provider-configurable."""

from __future__ import annotations

import re
from functools import lru_cache

from langchain_anthropic import ChatAnthropic
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, AIMessageChunk, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_openai import AzureChatOpenAI, AzureOpenAIEmbeddings, ChatOpenAI, OpenAIEmbeddings

from backend.app.config import Settings, get_settings
from backend.app.utils.logging import get_logger

logger = get_logger(__name__)

EXTRACTIVE_FALLBACK_PREFIX = (
    "AI generation is currently unavailable. "
    "Showing retrieved document information instead.\n\n"
)

GREETING_REPLY = (
    "Hello — I'm DocuMind. Ask a question about your uploaded PDFs "
    "(for example: what this document is about, or summarize a section)."
)
_GREETING_RE = re.compile(
    r"^(hi|hello|hey|thanks|thank you|good morning|good evening)[!?.]*$",
    re.IGNORECASE,
)


def is_greeting(message: str | None) -> bool:
    """True for short social greetings that should not run retrieval."""
    return bool(_GREETING_RE.fullmatch((message or "").strip()))



class ExtractiveChatModel(BaseChatModel):
    """
    Offline fallback LLM: synthesizes a short answer from the most relevant
    retrieved snippets without calling an external API.
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
        # BaseChatModel expects ChatGenerationChunk (with .message), not bare AIMessageChunk.
        text = self._extract_answer(messages)
        step = max(24, len(text) // 20 or 1)
        for i in range(0, len(text), step):
            yield ChatGenerationChunk(
                message=AIMessageChunk(content=text[i : i + step])
            )

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

        context = ""
        question = ""
        # Support both legacy and current prompt layouts
        if "Document context:" in human and "User question:" in human:
            ctx = human.split("Document context:", 1)[1]
            question_part = ctx.split("User question:", 1)
            context = question_part[0].strip()
            if len(question_part) > 1:
                question = question_part[1].split("Write a grounded answer", 1)[0].strip()
        elif "Context:" in human and "Question:" in human:
            ctx = human.split("Context:", 1)[1]
            question_part = ctx.split("Question:", 1)
            context = question_part[0].strip()
            question = (
                question_part[1].split("Answer:", 1)[0].strip()
                if len(question_part) > 1
                else ""
            )
        else:
            context = human
            question = ""

        # Prefer only Content: sections from labeled sources
        content_blocks: list[str] = []
        for block in context.split("---"):
            block = block.strip()
            if "Content:" in block:
                content_blocks.append(block.split("Content:", 1)[1].strip())
            elif block:
                content_blocks.append(block)

        q_probe = ""
        if "User question:" in human:
            q_probe = human.split("User question:", 1)[1].split("Write a grounded", 1)[0].strip().lower()
        if is_greeting(q_probe):
            return GREETING_REPLY

        if not content_blocks or sum(len(b) for b in content_blocks) < 20:
            return NOT_FOUND_MESSAGE

        def _clean(text: str) -> str:
            # Fix common PDF extraction artifacts (split words, runaway whitespace)
            text = text.replace("\u00ad", "")  # soft hyphen
            text = re.sub(r"(\w)-\s+(\w)", r"\1\2", text)
            text = re.sub(r"[ \t]+", " ", text)
            text = re.sub(r"\n{3,}", "\n\n", text)
            return text.strip()

        content_blocks = [_clean(b) for b in content_blocks if _clean(b)]

        def _words(text: str) -> set[str]:
            raw = re.findall(r"[a-z0-9]{3,}", text.lower())
            out: set[str] = set()
            for w in raw:
                out.add(w)
                if w.endswith("s") and len(w) > 4:
                    out.add(w[:-1])
                else:
                    out.add(w + "s")
            return out

        q_lower = question.lower()
        is_summary = bool(
            re.search(
                r"\b(summar(y|ise|ize)|main points?|key points?|overview|what is this|"
                r"about this document|tl;?dr|highlights)\b",
                q_lower,
            )
        )

        q_words = _words(question)
        stop = {
            "what", "which", "when", "where", "that", "this", "with", "from",
            "have", "does", "about", "your", "document", "documents", "please",
            "tell", "give", "list", "named", "name", "the", "and", "are",
            "was", "were", "for", "how", "who", "why", "any", "main", "points",
            "summarize", "summary", "overview", "key",
        }
        q_words -= stop

        def score(s: str) -> int:
            return len(q_words & _words(s)) if q_words else 0

        ranked = sorted(content_blocks, key=score, reverse=True)
        if not ranked:
            return NOT_FOUND_MESSAGE

        # --- Summary / overview: bullet points from several passages ---
        if is_summary:
            bullets: list[str] = []
            seen: set[str] = set()
            for block in ranked[:4]:
                sentences = [
                    s.strip()
                    for s in re.split(r"(?<=[.!?])\s+", block)
                    if len(s.strip()) > 40
                ]
                # Prefer the opening sentence of each chunk (usually section topic)
                pick = sentences[:2] if sentences else [block[:220]]
                for sent in pick:
                    key = sent[:80].lower()
                    if key in seen:
                        continue
                    seen.add(key)
                    if len(sent) > 220:
                        sent = sent[:220].rsplit(" ", 1)[0] + "…"
                    bullets.append(sent)
                    if len(bullets) >= 5:
                        break
                if len(bullets) >= 5:
                    break
            if not bullets:
                return NOT_FOUND_MESSAGE
            body = "\n".join(f"- {b}" for b in bullets)
            return (
                "**Document summary** (extractive · offline — enable `LLM_PROVIDER=openai` "
                "for a rewritten synthesis)\n\n"
                f"{body}\n\n"
                "_Based on the highest-ranked passages from your PDF. "
                "Open Sources below to verify._"
            )

        # --- Normal Q&A: concise lead from best-matching passage ---
        top = [t for t in ranked[:2] if t.strip()]
        primary = top[0]
        sentences = re.split(r"(?<=[.!?])\s+", primary)
        lead = " ".join(sentences[:3]).strip() if sentences else primary[:500]
        if len(lead) > 700:
            lead = lead[:700].rsplit(" ", 1)[0] + "…"
        extras = ""
        if len(top) > 1:
            extras = "\n\n**Related passage:**\n" + top[1][:450]
            if len(top[1]) > 450:
                extras += "…"
        return (
            "**Answer from your documents** (extractive · offline)\n\n"
            + lead
            + extras
        )


def get_chat_llm(settings: Settings | None = None, streaming: bool = False) -> BaseChatModel:
    """Return a chat LLM based on configured provider."""
    settings = settings or get_settings()
    provider = settings.llm_provider
    temperature = float(getattr(settings, "llm_temperature", 0.1) or 0.1)

    if provider == "extractive":
        return ExtractiveChatModel()

    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")
        return ChatOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_api_base,
            model=settings.openai_chat_model,
            temperature=temperature,
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
            temperature=temperature,
            streaming=streaming,
        )

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
        return ChatAnthropic(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_chat_model,
            temperature=temperature,
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
