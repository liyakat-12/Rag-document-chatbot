"""HTTP client for the RAG FastAPI backend (persistent keep-alive connection)."""

from __future__ import annotations

import json
from typing import Any, Generator, Optional

import httpx

DEFAULT_BASE = "http://localhost:8001/api/v1"


class RagClient:
    """Reuse one httpx.Client — opening a new TCP connection per call is a major UI lag source."""

    def __init__(self, base_url: str = DEFAULT_BASE, timeout: float = 300.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._client = httpx.Client(
            base_url=self.base_url,
            timeout=httpx.Timeout(timeout, connect=10.0),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

    def close(self) -> None:
        self._client.close()

    def _url(self, path: str) -> str:
        return path if path.startswith("/") else f"/{path}"

    def health(self) -> dict[str, Any]:
        # Short timeout so the sidebar never hangs on an unreachable host
        r = self._client.get(self._url("/health"), timeout=3.0)
        r.raise_for_status()
        return r.json()

    def list_documents(self) -> list[dict[str, Any]]:
        r = self._client.get(self._url("/documents"))
        r.raise_for_status()
        return r.json()

    def upload(self, files: list[tuple[str, bytes, str]]) -> dict[str, Any]:
        multipart = [
            ("files", (name, content, ctype or "application/pdf"))
            for name, content, ctype in files
        ]
        r = self._client.post(self._url("/upload"), files=multipart)
        if r.status_code >= 400:
            raise RuntimeError(_error_detail(r))
        return r.json()

    def delete_document(self, document_id: str) -> dict[str, Any]:
        r = self._client.delete(self._url(f"/document/{document_id}"))
        if r.status_code >= 400:
            raise RuntimeError(_error_detail(r))
        return r.json()

    def reindex(self) -> dict[str, Any]:
        r = self._client.post(self._url("/reindex"))
        if r.status_code >= 400:
            raise RuntimeError(_error_detail(r))
        return r.json()

    def list_sessions(self) -> list[dict[str, Any]]:
        r = self._client.get(self._url("/history"))
        r.raise_for_status()
        return r.json().get("sessions", [])

    def get_session(self, session_id: str) -> dict[str, Any]:
        r = self._client.get(self._url(f"/history/{session_id}"))
        if r.status_code >= 400:
            raise RuntimeError(_error_detail(r))
        return r.json()

    def delete_session(self, session_id: str) -> None:
        r = self._client.delete(self._url(f"/history/{session_id}"))
        if r.status_code >= 400:
            raise RuntimeError(_error_detail(r))

    def chat(
        self,
        message: str,
        session_id: Optional[str] = None,
        document_ids: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "message": message,
            "session_id": session_id,
            "stream": False,
        }
        if document_ids:
            payload["document_ids"] = document_ids
        r = self._client.post(self._url("/chat"), json=payload)
        if r.status_code >= 400:
            raise RuntimeError(_error_detail(r))
        return r.json()

    def chat_stream(
        self,
        message: str,
        session_id: Optional[str] = None,
        document_ids: Optional[list[str]] = None,
    ) -> Generator[dict[str, Any], None, None]:
        """Prefer non-stream chat for extractive — stream kept for cloud LLMs."""
        payload: dict[str, Any] = {
            "message": message,
            "session_id": session_id,
            "stream": True,
        }
        if document_ids:
            payload["document_ids"] = document_ids
        try:
            with self._client.stream("POST", self._url("/chat/stream"), json=payload) as response:
                if response.status_code >= 400:
                    response.read()
                    raise RuntimeError(_error_detail(response))
                buffer = ""
                for chunk in response.iter_text():
                    buffer += chunk
                    while "\n\n" in buffer:
                        part, buffer = buffer.split("\n\n", 1)
                        line = part.strip()
                        if not line.startswith("data:"):
                            continue
                        data = line[5:].strip()
                        if data == "[DONE]":
                            return
                        try:
                            yield json.loads(data)
                        except json.JSONDecodeError:
                            continue
        except httpx.RemoteProtocolError:
            result = self.chat(message, session_id=session_id, document_ids=document_ids)
            yield {
                "event": "meta",
                "session_id": result.get("session_id"),
                "sources": result.get("sources") or [],
                "confidence": result.get("confidence", 0),
                "cached": result.get("cached", False),
                "retrieved_chunks": result.get("retrieved_chunks") or result.get("sources") or [],
            }
            yield {"event": "token", "content": result.get("answer", "")}
            yield {
                "event": "done",
                "message_id": result.get("message_id"),
                "answer": result.get("answer", ""),
                "sources": result.get("sources") or [],
                "retrieved_chunks": result.get("retrieved_chunks") or [],
                "confidence": result.get("confidence", 0),
                "tokens_used": result.get("tokens_used", 0),
                "cached": result.get("cached", False),
                "retrieval": result.get("retrieval") or {},
                "timings": result.get("timings") or {},
            }

    def rate_message(self, message_id: str, rating: str) -> dict[str, Any]:
        r = self._client.post(
            self._url(f"/messages/{message_id}/rate"),
            json={"rating": rating},
        )
        if r.status_code >= 400:
            raise RuntimeError(_error_detail(r))
        return r.json()

    def export_pdf(self, session_id: str) -> bytes:
        r = self._client.get(self._url(f"/history/{session_id}/export"))
        if r.status_code >= 400:
            raise RuntimeError(_error_detail(r))
        return r.content

    def admin_stats(self) -> dict[str, Any]:
        r = self._client.get(self._url("/admin/stats"))
        r.raise_for_status()
        return r.json()

    def system_info(self) -> dict[str, Any]:
        r = self._client.get(self._url("/admin/system"), timeout=10.0)
        r.raise_for_status()
        return r.json()


def _error_detail(response: httpx.Response) -> str:
    try:
        body = response.json()
        detail = body.get("detail", body)
        if isinstance(detail, str):
            return detail
        return json.dumps(detail)
    except Exception:
        return response.text or response.reason_phrase or "Request failed"
