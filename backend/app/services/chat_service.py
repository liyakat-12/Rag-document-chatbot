"""Chat session, memory, summarization, and QA orchestration."""

from __future__ import annotations

import json
import time
from collections.abc import AsyncIterator
from typing import Any, Optional
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from backend.app.db.models import ChatMessage, ChatSession
from backend.app.rag.llm_factory import get_chat_llm
from backend.app.rag.qa_chain import (
    NOT_FOUND_MESSAGE,
    build_qa_result,
    expand_followup_query,
    generate_answer,
    retrieve_detailed,
    stream_answer,
)
from backend.app.rag.semantic_cache import lookup_cache, store_cache
from backend.app.utils.logging import get_logger
from backend.app.utils.titles import make_conversation_title
from backend.app.utils.tokens import count_tokens

logger = get_logger(__name__)


async def create_session(session: AsyncSession, title: str = "New Chat") -> ChatSession:
    chat = ChatSession(title=title)
    session.add(chat)
    await session.flush()
    loaded = await get_session(session, chat.id)
    return loaded or chat


async def get_session(session: AsyncSession, session_id: str) -> ChatSession | None:
    result = await session.execute(
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(ChatSession.id == session_id)
    )
    return result.scalar_one_or_none()


async def list_sessions(session: AsyncSession) -> list[dict[str, Any]]:
    result = await session.execute(select(ChatSession).order_by(ChatSession.updated_at.desc()))
    sessions = list(result.scalars().all())
    out: list[dict[str, Any]] = []
    for s in sessions:
        count = await session.scalar(
            select(func.count()).select_from(ChatMessage).where(ChatMessage.session_id == s.id)
        )
        out.append(
            {
                "id": s.id,
                "title": s.title,
                "summary": s.summary,
                "created_at": s.created_at,
                "updated_at": s.updated_at,
                "message_count": count or 0,
            }
        )
    return out


async def delete_session(session: AsyncSession, session_id: str) -> bool:
    chat = await get_session(session, session_id)
    if not chat:
        return False
    await session.delete(chat)
    return True


async def _ensure_session(session: AsyncSession, session_id: Optional[str], first_message: str) -> ChatSession:
    if session_id:
        chat = await get_session(session, session_id)
        if chat:
            return chat
    title = make_conversation_title(first_message)
    return await create_session(session, title=title)


async def _load_messages(session: AsyncSession, chat_id: str) -> list[ChatMessage]:
    result = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == chat_id)
        .order_by(ChatMessage.created_at)
    )
    return list(result.scalars().all())


def _format_recent_history(messages: list[ChatMessage], exclude_last: bool = True) -> str:
    """Compact recent turns for the QA prompt (not a full transcript dump)."""
    usable = messages[:-1] if exclude_last and messages else messages
    recent = usable[-6:]
    if not recent:
        return ""
    lines: list[str] = []
    for m in recent:
        role = m.role
        content = (m.content or "")[:400]
        lines.append(f"{role}: {content}")
    return "\n".join(lines)


def _prior_user_questions(messages: list[ChatMessage]) -> list[str]:
    """User questions before the latest turn (latest is the current question)."""
    users = [m.content for m in messages if m.role == "user"]
    return users[:-1] if len(users) > 1 else []


async def summarize_if_needed(session: AsyncSession, chat: ChatSession) -> str:
    """Summarize older turns when conversation grows long."""
    from backend.app.config import get_settings

    if get_settings().llm_provider == "extractive":
        # Offline mode: build a tiny extractive summary from recent turns
        messages = await _load_messages(session, chat.id)
        history = _format_recent_history(messages, exclude_last=True)
        return history[:800] or (chat.summary or "")

    messages = await _load_messages(session, chat.id)
    if len(messages) < 8:
        return chat.summary or ""

    if chat.summary and len(messages) % 6 != 0:
        return chat.summary

    history_text = "\n".join(f"{m.role}: {m.content[:500]}" for m in messages[-12:])
    try:
        llm = get_chat_llm(streaming=False)
        prompt = (
            "Summarize this conversation in 3-5 concise sentences, "
            "preserving key facts and user intent:\n\n" + history_text
        )
        response = await llm.ainvoke(prompt)
        summary = (response.content or "").strip()
        chat.summary = summary
        await session.flush()
        return summary
    except Exception as exc:
        logger.warning("summarization_failed", error=str(exc))
        return chat.summary or ""


async def chat(
    session: AsyncSession,
    message: str,
    session_id: Optional[str] = None,
    document_ids: Optional[list[str]] = None,
) -> dict[str, Any]:
    """Non-streaming chat turn with memory, cache, citations, confidence."""
    t_total = time.perf_counter()
    chat_session = await _ensure_session(session, session_id, message)

    user_msg = ChatMessage(
        id=str(uuid4()),
        session_id=chat_session.id,
        role="user",
        content=message,
        tokens_used=count_tokens(message),
    )
    session.add(user_msg)
    await session.flush()

    cached = await lookup_cache(session, message)
    if cached:
        result = build_qa_result(
            answer=cached["answer"],
            docs_with_scores=[],
            tokens_used=0,
            cached=True,
            retrieval={"strategy": "semantic_cache", "latency_ms": 0},
        )
        result["sources"] = cached["sources"]
        result["retrieved_chunks"] = cached["sources"]
        result["confidence"] = cached["confidence"]
    else:
        messages = await _load_messages(session, chat_session.id)
        summary = await summarize_if_needed(session, chat_session)
        history = _format_recent_history(messages, exclude_last=True)
        retrieval_query = expand_followup_query(message, _prior_user_questions(messages))

        t_ret = time.perf_counter()
        detailed = await retrieve_detailed(retrieval_query, document_ids=document_ids)
        retrieval_ms = (time.perf_counter() - t_ret) * 1000
        docs = detailed.results
        retrieval_meta = {
            **detailed.details,
            "retrieval_query": retrieval_query if retrieval_query != message else None,
            "latency_ms": round(retrieval_ms, 2),
        }

        t_gen = time.perf_counter()
        answer, tokens = await generate_answer(
            message, docs, summary=summary, history=history
        )
        generation_ms = (time.perf_counter() - t_gen) * 1000
        result = build_qa_result(
            answer, docs, tokens_used=tokens, cached=False, retrieval=retrieval_meta
        )
        result["timings"] = {
            "retrieval_ms": round(retrieval_ms, 2),
            "generation_ms": round(generation_ms, 2),
            "total_ms": round((time.perf_counter() - t_total) * 1000, 2),
        }
        if answer != NOT_FOUND_MESSAGE:
            await store_cache(
                session,
                message,
                answer,
                result["sources"],
                result["confidence"],
            )
        logger.info(
            "chat_completed",
            session_id=chat_session.id,
            retrieval_ms=round(retrieval_ms, 2),
            generation_ms=round(generation_ms, 2),
            chunks=len(docs),
            cached=False,
        )

    assistant_msg = ChatMessage(
        id=str(uuid4()),
        session_id=chat_session.id,
        role="assistant",
        content=result["answer"],
        sources_json=json.dumps(result["sources"]),
        confidence=result["confidence"],
        tokens_used=result["tokens_used"],
    )
    session.add(assistant_msg)
    await session.flush()

    return {
        "session_id": chat_session.id,
        "message_id": assistant_msg.id,
        **result,
    }


async def chat_stream(
    session: AsyncSession,
    message: str,
    session_id: Optional[str] = None,
    document_ids: Optional[list[str]] = None,
) -> AsyncIterator[dict[str, Any]]:
    """
    Streaming chat. Yields event dicts:
      {"event": "meta", ...}
      {"event": "token", "content": "..."}
      {"event": "done", ...}
    """
    t_total = time.perf_counter()
    chat_session = await _ensure_session(session, session_id, message)

    user_msg = ChatMessage(
        id=str(uuid4()),
        session_id=chat_session.id,
        role="user",
        content=message,
        tokens_used=count_tokens(message),
    )
    session.add(user_msg)
    await session.flush()

    cached = await lookup_cache(session, message)
    if cached:
        yield {
            "event": "meta",
            "session_id": chat_session.id,
            "sources": cached["sources"],
            "confidence": cached["confidence"],
            "cached": True,
            "retrieval": {"strategy": "semantic_cache"},
        }
        yield {"event": "token", "content": cached["answer"]}
        assistant_msg = ChatMessage(
            id=str(uuid4()),
            session_id=chat_session.id,
            role="assistant",
            content=cached["answer"],
            sources_json=json.dumps(cached["sources"]),
            confidence=cached["confidence"],
            tokens_used=0,
        )
        session.add(assistant_msg)
        await session.flush()
        yield {
            "event": "done",
            "message_id": assistant_msg.id,
            "answer": cached["answer"],
            "sources": cached["sources"],
            "confidence": cached["confidence"],
            "tokens_used": 0,
            "cached": True,
            "timings": {"total_ms": round((time.perf_counter() - t_total) * 1000, 2)},
        }
        return

    messages = await _load_messages(session, chat_session.id)
    summary = await summarize_if_needed(session, chat_session)
    history = _format_recent_history(messages, exclude_last=True)
    retrieval_query = expand_followup_query(message, _prior_user_questions(messages))

    t_ret = time.perf_counter()
    detailed = await retrieve_detailed(retrieval_query, document_ids=document_ids)
    retrieval_ms = (time.perf_counter() - t_ret) * 1000
    docs = detailed.results
    retrieval_meta = {
        **detailed.details,
        "retrieval_query": retrieval_query if retrieval_query != message else None,
        "latency_ms": round(retrieval_ms, 2),
    }
    result_shell = build_qa_result("", docs, tokens_used=0, retrieval=retrieval_meta)

    yield {
        "event": "meta",
        "session_id": chat_session.id,
        "sources": result_shell["sources"],
        "confidence": 0.0,
        "cached": False,
        "retrieved_chunks": result_shell["retrieved_chunks"],
        "retrieval": retrieval_meta,
    }

    t_gen = time.perf_counter()
    parts: list[str] = []
    async for token in stream_answer(message, docs, summary=summary, history=history):
        parts.append(token)
        yield {"event": "token", "content": token}
    generation_ms = (time.perf_counter() - t_gen) * 1000

    answer = "".join(parts).strip() or NOT_FOUND_MESSAGE
    tokens_used = count_tokens(message) + count_tokens(answer)
    from backend.app.rag.qa_chain import compute_confidence

    confidence = compute_confidence(docs, answer)

    if answer != NOT_FOUND_MESSAGE:
        await store_cache(session, message, answer, result_shell["sources"], confidence)

    assistant_msg = ChatMessage(
        id=str(uuid4()),
        session_id=chat_session.id,
        role="assistant",
        content=answer,
        sources_json=json.dumps(result_shell["sources"]),
        confidence=confidence,
        tokens_used=tokens_used,
    )
    session.add(assistant_msg)
    await session.flush()

    timings = {
        "retrieval_ms": round(retrieval_ms, 2),
        "generation_ms": round(generation_ms, 2),
        "total_ms": round((time.perf_counter() - t_total) * 1000, 2),
    }
    logger.info(
        "chat_stream_completed",
        session_id=chat_session.id,
        retrieval_ms=timings["retrieval_ms"],
        generation_ms=timings["generation_ms"],
        chunks=len(docs),
        cached=False,
    )

    yield {
        "event": "done",
        "message_id": assistant_msg.id,
        "answer": answer,
        "sources": result_shell["sources"],
        "retrieved_chunks": result_shell["retrieved_chunks"],
        "confidence": confidence,
        "tokens_used": tokens_used,
        "cached": False,
        "retrieval": retrieval_meta,
        "timings": timings,
    }


async def rate_message(session: AsyncSession, message_id: str, rating: str) -> ChatMessage | None:
    result = await session.execute(select(ChatMessage).where(ChatMessage.id == message_id))
    msg = result.scalar_one_or_none()
    if not msg:
        return None
    msg.rating = rating
    await session.flush()
    return msg


async def admin_stats(session: AsyncSession) -> dict[str, Any]:
    from backend.app.rag.semantic_cache import get_cache_stats
    from backend.app.services.document_service import document_stats

    docs = await document_stats(session)
    sessions = await session.scalar(select(func.count()).select_from(ChatSession)) or 0
    messages = await session.scalar(select(func.count()).select_from(ChatMessage)) or 0
    tokens = await session.scalar(
        select(func.coalesce(func.sum(ChatMessage.tokens_used), 0))
    ) or 0
    answered = await session.scalar(
        select(func.count())
        .select_from(ChatMessage)
        .where(ChatMessage.role == "assistant")
    ) or 0
    feedback_up = await session.scalar(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.rating == "up")
    ) or 0
    feedback_down = await session.scalar(
        select(func.count()).select_from(ChatMessage).where(ChatMessage.rating == "down")
    ) or 0
    cache = get_cache_stats()
    return {
        "documents": docs,
        "total_sessions": sessions,
        "total_messages": messages,
        "total_tokens_used": tokens,
        "questions_answered": answered,
        "feedback_up": feedback_up,
        "feedback_down": feedback_down,
        **cache,
    }
