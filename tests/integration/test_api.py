"""Integration tests for API endpoints (no live LLM required for health/history)."""

import io

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health(client: AsyncClient):
    res = await client.get("/api/v1/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ok"
    assert "llm_provider" in data


@pytest.mark.asyncio
async def test_history_empty(client: AsyncClient):
    res = await client.get("/api/v1/history")
    assert res.status_code == 200
    assert res.json()["sessions"] == []


@pytest.mark.asyncio
async def test_documents_empty(client: AsyncClient):
    res = await client.get("/api/v1/documents")
    assert res.status_code == 200
    assert res.json() == []


@pytest.mark.asyncio
async def test_upload_rejects_non_pdf(client: AsyncClient):
    files = [("files", ("notes.txt", io.BytesIO(b"hello"), "text/plain"))]
    res = await client.post("/api/v1/upload", files=files)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_upload_rejects_fake_pdf(client: AsyncClient):
    files = [("files", ("fake.pdf", io.BytesIO(b"not-a-pdf"), "application/pdf"))]
    res = await client.post("/api/v1/upload", files=files)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_admin_stats(client: AsyncClient):
    res = await client.get("/api/v1/admin/stats")
    assert res.status_code == 200
    data = res.json()
    assert "documents" in data
    assert "total_sessions" in data


@pytest.mark.asyncio
async def test_delete_missing_document(client: AsyncClient):
    res = await client.delete("/api/v1/document/does-not-exist")
    assert res.status_code == 404
