"""Chat API routes: chat, history, rating, export, streaming."""

from __future__ import annotations

import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.db.session import get_db
from backend.app.models.schemas import (
    ChatRequest,
    ChatResponse,
    HistoryResponse,
    MessageOut,
    RateRequest,
    SessionDetail,
    SessionOut,
)
from backend.app.services import chat_service
from backend.app.services.export_service import export_conversation_pdf

router = APIRouter(tags=["chat"])


@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(body: ChatRequest, db: AsyncSession = Depends(get_db)) -> ChatResponse:
    """Non-streaming chat (set stream=false). For streaming use /chat/stream."""
    if body.stream:
        raise HTTPException(
            status_code=400,
            detail="Use POST /chat/stream for streaming responses, or set stream=false.",
        )
    result = await chat_service.chat(
        db,
        message=body.message,
        session_id=body.session_id,
        document_ids=body.document_ids,
    )
    return ChatResponse(**result)


@router.post("/chat/stream")
async def chat_stream_endpoint(body: ChatRequest) -> StreamingResponse:
    """SSE streaming chat responses (owns its DB session for the full stream)."""
    from backend.app.db.session import AsyncSessionLocal

    async def event_generator():
        async with AsyncSessionLocal() as db:
            try:
                async for event in chat_service.chat_stream(
                    db,
                    message=body.message,
                    session_id=body.session_id,
                    document_ids=body.document_ids,
                ):
                    yield f"data: {json.dumps(event)}\n\n"
                await db.commit()
            except Exception as exc:
                await db.rollback()
                # Send error event instead of silently closing the stream
                yield f"data: {json.dumps({'event': 'error', 'content': str(exc)})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/history", response_model=HistoryResponse)
async def history(db: AsyncSession = Depends(get_db)) -> HistoryResponse:
    sessions = await chat_service.list_sessions(db)
    return HistoryResponse(sessions=[SessionOut(**s) for s in sessions])


@router.get("/history/{session_id}", response_model=SessionDetail)
async def session_detail(session_id: str, db: AsyncSession = Depends(get_db)) -> SessionDetail:
    chat = await chat_service.get_session(db, session_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Session not found.")
    messages = []
    for m in chat.messages:
        sources = json.loads(m.sources_json) if m.sources_json else None
        messages.append(
            MessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                sources=sources,
                confidence=m.confidence,
                rating=m.rating,
                tokens_used=m.tokens_used,
                created_at=m.created_at,
            )
        )
    return SessionDetail(
        id=chat.id,
        title=chat.title,
        summary=chat.summary,
        created_at=chat.created_at,
        updated_at=chat.updated_at,
        message_count=len(messages),
        messages=messages,
    )


@router.delete("/history/{session_id}")
async def delete_history(session_id: str, db: AsyncSession = Depends(get_db)) -> dict:
    ok = await chat_service.delete_session(db, session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"message": "Session deleted.", "id": session_id}


@router.post("/messages/{message_id}/rate")
async def rate_answer(
    message_id: str,
    body: RateRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    msg = await chat_service.rate_message(db, message_id, body.rating.value)
    if not msg:
        raise HTTPException(status_code=404, detail="Message not found.")
    return {"message_id": message_id, "rating": msg.rating}


@router.get("/history/{session_id}/export")
async def export_session(session_id: str, db: AsyncSession = Depends(get_db)) -> Response:
    chat = await chat_service.get_session(db, session_id)
    if not chat:
        raise HTTPException(status_code=404, detail="Session not found.")
    payload = [
        {"role": m.role, "content": m.content, "confidence": m.confidence}
        for m in chat.messages
    ]
    pdf_bytes = export_conversation_pdf(chat.title, payload)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="chat-{session_id[:8]}.pdf"'},
    )
