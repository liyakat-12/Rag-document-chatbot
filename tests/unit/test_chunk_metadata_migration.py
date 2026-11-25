"""Chunk metadata enrichment + SQLite migration on a copy of a live DB."""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path

import pytest
from langchain_core.documents import Document as LCDocument

from backend.app.db.migrate import migrate_sqlite_file
from backend.app.rag.ingest import split_documents

ROOT = Path(__file__).resolve().parents[2]
LIVE_DB = ROOT / "data" / "chatbot.db"
SRC_COPY = ROOT / "data" / "_migration_test_src.db"


def _make_legacy_db(path: Path) -> None:
    """Minimal pre-migration schema with one PDF document + chunk."""
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(str(path))
    conn.executescript(
        """
        CREATE TABLE documents (
          id TEXT PRIMARY KEY,
          filename TEXT NOT NULL,
          original_filename TEXT NOT NULL,
          file_path TEXT NOT NULL,
          file_size INTEGER DEFAULT 0,
          page_count INTEGER DEFAULT 0,
          chunk_count INTEGER DEFAULT 0,
          status TEXT DEFAULT 'indexed',
          error_message TEXT,
          created_at DATETIME,
          updated_at DATETIME
        );
        CREATE TABLE document_chunks (
          id TEXT PRIMARY KEY,
          document_id TEXT NOT NULL,
          chunk_index INTEGER NOT NULL,
          page_number INTEGER DEFAULT 1,
          content TEXT NOT NULL,
          token_count INTEGER DEFAULT 0,
          faiss_id INTEGER,
          created_at DATETIME
        );
        INSERT INTO documents VALUES (
          'doc-legacy-1', 'stored.pdf', 'sid_example.pdf', 'uploads/stored.pdf',
          100, 2, 1, 'indexed', NULL,
          '2026-01-01 00:00:00', '2026-01-01 00:00:00'
        );
        INSERT INTO document_chunks VALUES (
          'doc-legacy-1_0', 'doc-legacy-1', 0, 3,
          'Scheme code example text', 4, NULL, '2026-01-01 00:00:00'
        );
        """
    )
    conn.commit()
    conn.close()


def test_split_documents_emits_full_metadata():
    pages = [
        LCDocument(page_content="Alpha beta gamma " * 20, metadata={"page": 0}),
        LCDocument(page_content="Delta epsilon " * 20, metadata={"page": 1}),
    ]
    chunks = split_documents(
        pages,
        document_id="abc",
        filename="fund.pdf",
        file_type="pdf",
        extraction_method="text",
        uploaded_at="2026-11-13T00:00:00+00:00",
    )
    assert chunks
    meta = chunks[0].metadata
    for key in (
        "document_id",
        "filename",
        "file_type",
        "location_type",
        "location",
        "chunk_id",
        "parent_chunk_id",
        "extraction_method",
        "uploaded_at",
    ):
        assert key in meta
    assert meta["document_id"] == "abc"
    assert meta["filename"] == "fund.pdf"
    assert meta["file_type"] == "pdf"
    assert meta["location_type"] == "page"
    assert meta["location"] == "1"
    assert meta["chunk_id"] == "abc_0"
    assert meta["parent_chunk_id"] is None
    assert meta["extraction_method"] == "text"
    assert meta["uploaded_at"]


def test_migration_on_synthetic_legacy_db(tmp_path):
    db = tmp_path / "legacy.db"
    _make_legacy_db(db)
    before = sqlite3.connect(str(db))
    cols_before = {r[1] for r in before.execute("PRAGMA table_info(document_chunks)").fetchall()}
    before.close()
    assert "file_type" not in cols_before

    stats = migrate_sqlite_file(db)
    assert "file_type" in stats["added_chunk_cols"] or stats["backfilled"] >= 0

    conn = sqlite3.connect(str(db))
    cols = {r[1] for r in conn.execute("PRAGMA table_info(document_chunks)").fetchall()}
    for required in (
        "filename",
        "file_type",
        "location_type",
        "location",
        "parent_chunk_id",
        "extraction_method",
        "uploaded_at",
    ):
        assert required in cols
    row = conn.execute(
        "SELECT filename, file_type, location_type, location, extraction_method, parent_chunk_id "
        "FROM document_chunks WHERE id='doc-legacy-1_0'"
    ).fetchone()
    conn.close()
    assert row[0] == "sid_example.pdf"
    assert row[1] == "pdf"
    assert row[2] == "page"
    assert row[3] == "3"
    assert row[4] == "text"
    assert row[5] is None


def test_migration_on_copy_of_live_database(tmp_path):
    """Copy the real chatbot.db (or prepared src copy) and migrate without touching live."""
    src = SRC_COPY if SRC_COPY.is_file() else LIVE_DB
    if not src.is_file():
        pytest.skip("no live chatbot.db to copy")
    dest = tmp_path / "chatbot_copy.db"
    shutil.copy2(src, dest)

    # Count chunks before
    conn = sqlite3.connect(str(dest))
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if "document_chunks" not in tables:
        conn.close()
        pytest.skip("copied DB has no document_chunks")
    n_before = conn.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0]
    content_sample = conn.execute(
        "SELECT id, content FROM document_chunks LIMIT 1"
    ).fetchone()
    conn.close()

    stats = migrate_sqlite_file(dest)
    assert stats["path"]

    conn = sqlite3.connect(str(dest))
    n_after = conn.execute("SELECT COUNT(*) FROM document_chunks").fetchone()[0]
    assert n_after == n_before
    # Old rows still readable; new cols populated as text PDFs
    rows = conn.execute(
        "SELECT file_type, location_type, extraction_method, location FROM document_chunks LIMIT 20"
    ).fetchall()
    conn.close()
    assert rows
    for ft, lt, em, loc in rows:
        assert ft == "pdf"
        assert lt == "page"
        assert em == "text"
        assert loc is not None and str(loc) != ""
    if content_sample:
        # Content untouched
        conn = sqlite3.connect(str(dest))
        again = conn.execute(
            "SELECT content FROM document_chunks WHERE id=?", (content_sample[0],)
        ).fetchone()
        conn.close()
        assert again[0] == content_sample[1]


def test_migration_idempotent(tmp_path):
    db = tmp_path / "legacy.db"
    _make_legacy_db(db)
    migrate_sqlite_file(db)
    stats2 = migrate_sqlite_file(db)
    assert stats2["added_chunk_cols"] == []
