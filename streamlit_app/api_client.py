"""HTTP client for the RAG FastAPI backend."""

from __future__ import annotations

import json
from typing import Any, Generator, Optional

import httpx

DEFAULT_BASE = "http://localhost:8000/api/v1"


class RagClient:
    def __init__(self, base_url: str = DEFAULT_BASE, timeout: float = 300.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def health(self) -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(self._url("/health"))
            r.raise_for_status()
            return r.json()

    def list_documents(self) -> list[dict[str, Any]]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(self._url("/documents"))
            r.raise_for_status()
            return r.json()

    def upload(self, files: list[tuple[str, bytes, str]]) -> dict[str, Any]:
        """files: list of (filename, content_bytes, content_type)."""
        multipart = [
            ("files", (name, content, ctype or "application/pdf"))
            for name, content, ctype in files
        ]
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(self._url("/upload"), files=multipart)
            if r.status_code >= 400:
                detail = _error_detail(r)
                raise RuntimeError(detail)
            return r.json()

    def delete_document(self, document_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.delete(self._url(f"/document/{document_id}"))
            if r.status_code >= 400:
                raise RuntimeError(_error_detail(r))
            return r.json()

    def reindex(self) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(self._url("/reindex"))
            if r.status_code >= 400:
                raise RuntimeError(_error_detail(r))
            return r.json()

    def list_sessions(self) -> list[dict[str, Any]]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(self._url("/history"))
            r.raise_for_status()
            return r.json().get("sessions", [])

    def get_session(self, session_id: str) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(self._url(f"/history/{session_id}"))
            if r.status_code >= 400:
                raise RuntimeError(_error_detail(r))
            return r.json()

    def delete_session(self, session_id: str) -> None:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.delete(self._url(f"/history/{session_id}"))
            if r.status_code >= 400:
                raise RuntimeError(_error_detail(r))

    def chat(self, message: str, session_id: Optional[str] = None) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(
                self._url("/chat"),
                json={"message": message, "session_id": session_id, "stream": False},
            )
            if r.status_code >= 400:
                raise RuntimeError(_error_detail(r))
            return r.json()

    def chat_stream(
        self, message: str, session_id: Optional[str] = None
    ) -> Generator[dict[str, Any], None, None]:
        try:
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream(
                    "POST",
                    self._url("/chat/stream"),
                    json={"message": message, "session_id": session_id, "stream": True},
                ) as response:
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
            # Backend closed stream early — fall back to non-streaming chat
            result = self.chat(message, session_id=session_id)
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
        with httpx.Client(timeout=self.timeout) as client:
            r = client.post(
                self._url(f"/messages/{message_id}/rate"),
                json={"rating": rating},
            )
            if r.status_code >= 400:
                raise RuntimeError(_error_detail(r))
            return r.json()

    def export_pdf(self, session_id: str) -> bytes:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(self._url(f"/history/{session_id}/export"))
            if r.status_code >= 400:
                raise RuntimeError(_error_detail(r))
            return r.content

    def admin_stats(self) -> dict[str, Any]:
        with httpx.Client(timeout=self.timeout) as client:
            r = client.get(self._url("/admin/stats"))
            r.raise_for_status()
            return r.json()

    def system_info(self) -> dict[str, Any]:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(self._url("/admin/system"))
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
