"""RetrievalQA pipeline with grounded prompting, citations, and confidence."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any, Optional

from langchain_core.documents import Document as LCDocument
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate

from backend.app.config import get_settings
from backend.app.models.schemas import SourceCitation
from backend.app.rag.hybrid_search import hybrid_search
from backend.app.rag.llm_factory import get_chat_llm
from backend.app.utils.logging import get_logger
from backend.app.utils.tokens import count_tokens, truncate_to_token_budget

logger = get_logger(__name__)

NOT_FOUND_MESSAGE = "I couldn't find that information in the uploaded documents."

SYSTEM_PROMPT = """You are a careful document Q&A assistant.
You MUST answer ONLY using the provided context from uploaded documents.
If the context does not contain enough information to answer, respond EXACTLY with:
I couldn't find that information in the uploaded documents.

Rules:
- Never invent facts, numbers, or citations.
- Use only the retrieved context.
- Cite sources inline using [filename, p.N] when making claims.
- Be concise and accurate.
- If the question is unrelated to the documents, use the exact not-found message above.
"""

QA_PROMPT = ChatPromptTemplate.from_messages(
    [
        ("system", SYSTEM_PROMPT),
        (
            "human",
            "Conversation summary (optional):\n{summary}\n\n"
            "Context:\n{context}\n\n"
            "Question: {question}\n\n"
            "Answer:",
        ),
    ]
)


def _format_context(docs_with_scores: list[tuple[LCDocument, float]]) -> str:
    parts: list[str] = []
    for i, (doc, score) in enumerate(docs_with_scores, start=1):
        meta = doc.metadata
        header = (
            f"[{i}] file={meta.get('filename', 'unknown')} "
            f"page={meta.get('page_number', '?')} "
            f"chunk={meta.get('chunk_id', '?')} "
            f"score={score:.3f}"
        )
        parts.append(f"{header}\n{doc.page_content}")
    return "\n\n---\n\n".join(parts)


def _to_citations(docs_with_scores: list[tuple[LCDocument, float]]) -> list[SourceCitation]:
    citations: list[SourceCitation] = []
    for doc, score in docs_with_scores:
        meta = doc.metadata
        citations.append(
            SourceCitation(
                document_id=str(meta.get("document_id", "")),
                filename=str(meta.get("filename", "unknown")),
                page_number=int(meta.get("page_number", 1)),
                chunk_id=str(meta.get("chunk_id", "")),
                content=doc.page_content,
                score=round(float(score), 4),
            )
        )
    return citations


def compute_confidence(
    docs_with_scores: list[tuple[LCDocument, float]],
    answer: str,
) -> float:
    """Heuristic confidence from retrieval scores + answer grounding."""
    if not docs_with_scores or answer.strip() == NOT_FOUND_MESSAGE:
        return 0.0
    scores = [s for _, s in docs_with_scores]
    avg = sum(scores) / len(scores)
    # Boost if top score is strong
    top = scores[0]
    confidence = min(1.0, 0.6 * top + 0.4 * avg)
    return round(confidence, 3)


async def retrieve(
    question: str,
    document_ids: Optional[list[str]] = None,
) -> list[tuple[LCDocument, float]]:
    """Run hybrid retrieval for a question."""
    return hybrid_search(question, document_ids=document_ids)


async def generate_answer(
    question: str,
    docs_with_scores: list[tuple[LCDocument, float]],
    summary: str = "",
) -> tuple[str, int]:
    """Generate a grounded answer. Returns (answer, tokens_used)."""
    settings = get_settings()
    if not docs_with_scores:
        return NOT_FOUND_MESSAGE, 0

    context = _format_context(docs_with_scores)
    context = truncate_to_token_budget(context, settings.token_budget_per_request // 2)

    llm = get_chat_llm(streaming=False)
    messages = QA_PROMPT.format_messages(
        summary=summary or "(none)",
        context=context,
        question=question,
    )
    response = await llm.ainvoke(messages)
    answer = (response.content or "").strip()
    if not answer:
        answer = NOT_FOUND_MESSAGE

    tokens = count_tokens(question) + count_tokens(context) + count_tokens(answer)
    return answer, tokens


async def stream_answer(
    question: str,
    docs_with_scores: list[tuple[LCDocument, float]],
    summary: str = "",
) -> AsyncIterator[str]:
    """Stream a grounded answer token-by-token."""
    settings = get_settings()
    if not docs_with_scores:
        yield NOT_FOUND_MESSAGE
        return

    context = _format_context(docs_with_scores)
    context = truncate_to_token_budget(context, settings.token_budget_per_request // 2)

    llm = get_chat_llm(streaming=True)
    messages = QA_PROMPT.format_messages(
        summary=summary or "(none)",
        context=context,
        question=question,
    )
    async for chunk in llm.astream(messages):
        text = chunk.content
        if isinstance(text, str) and text:
            yield text


def build_qa_result(
    answer: str,
    docs_with_scores: list[tuple[LCDocument, float]],
    tokens_used: int = 0,
    cached: bool = False,
) -> dict[str, Any]:
    """Package answer + sources + confidence for API responses."""
    citations = _to_citations(docs_with_scores)
    confidence = compute_confidence(docs_with_scores, answer)
    return {
        "answer": answer,
        "sources": [c.model_dump() for c in citations],
        "retrieved_chunks": [c.model_dump() for c in citations],
        "confidence": confidence,
        "tokens_used": tokens_used,
        "cached": cached,
    }
