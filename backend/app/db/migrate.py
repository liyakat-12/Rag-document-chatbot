"""Lightweight SQLite schema migrations (no Alembic).

Adds chunk metadata columns and backfills existing PDF rows as
file_type=pdf, location_type=page, extraction_method=text.
Safe to run repeatedly.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable

from backend.app.utils.logging import get_logger

logger = get_logger(__name__)

# Columns added to document_chunks (name, SQL type, default for ADD COLUMN)
_CHUNK_COLUMNS: list[tuple[str, str, str | None]] = [
    ("filename", "VARCHAR(512)", "''"),
    ("file_type", "VARCHAR(32)", "'pdf'"),
    ("location_type", "VARCHAR(32)", "'page'"),
    ("location", "VARCHAR(512)", "''"),
    ("parent_chunk_id", "VARCHAR(64)", None),
    ("extraction_method", "VARCHAR(32)", "'text'"),
    ("uploaded_at", "DATETIME", None),
]

_DOC_COLUMNS: list[tuple[str, str, str | None]] = [
    ("file_type", "VARCHAR(32)", "'pdf'"),
    ("extraction_method", "VARCHAR(32)", "'text'"),
]


def _existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def _add_missing_columns(
    conn: sqlite3.Connection,
    table: str,
    columns: Iterable[tuple[str, str, str | None]],
) -> list[str]:
    existing = _existing_columns(conn, table)
    added: list[str] = []
    for name, sql_type, default in columns:
        if name in existing:
            continue
        if default is None:
            ddl = f"ALTER TABLE {table} ADD COLUMN {name} {sql_type}"
        else:
            ddl = f"ALTER TABLE {table} ADD COLUMN {name} {sql_type} DEFAULT {default}"
        conn.execute(ddl)
        added.append(name)
    return added


def migrate_sqlite_file(db_path: Path | str) -> dict:
    """Apply migrations to a SQLite file. Returns a small stats dict."""
    path = Path(db_path)
    if not path.is_file():
        raise FileNotFoundError(f"Database not found: {path}")

    conn = sqlite3.connect(str(path))
    try:
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        stats: dict = {"path": str(path), "added_chunk_cols": [], "added_doc_cols": [], "backfilled": 0}
        if "document_chunks" not in tables:
            logger.info("migrate_skip_no_chunks_table", path=str(path))
            return stats

        stats["added_chunk_cols"] = _add_missing_columns(conn, "document_chunks", _CHUNK_COLUMNS)
        if "documents" in tables:
            stats["added_doc_cols"] = _add_missing_columns(conn, "documents", _DOC_COLUMNS)

        # Backfill existing PDF chunks as text extraction with page locations
        # Join documents for filename + created_at when available
        if "documents" in tables:
            conn.execute(
                """
                UPDATE document_chunks
                SET
                  filename = COALESCE(
                    NULLIF(filename, ''),
                    (SELECT original_filename FROM documents d WHERE d.id = document_chunks.document_id),
                    ''
                  ),
                  file_type = COALESCE(NULLIF(file_type, ''), 'pdf'),
                  location_type = COALESCE(NULLIF(location_type, ''), 'page'),
                  location = CASE
                    WHEN location IS NULL OR location = '' THEN CAST(page_number AS TEXT)
                    ELSE location
                  END,
                  extraction_method = COALESCE(NULLIF(extraction_method, ''), 'text'),
                  uploaded_at = COALESCE(
                    uploaded_at,
                    (SELECT created_at FROM documents d WHERE d.id = document_chunks.document_id),
                    created_at
                  )
                """
            )
            conn.execute(
                """
                UPDATE documents
                SET
                  file_type = COALESCE(NULLIF(file_type, ''), 'pdf'),
                  extraction_method = COALESCE(NULLIF(extraction_method, ''), 'text')
                """
            )
        else:
            conn.execute(
                """
                UPDATE document_chunks
                SET
                  file_type = COALESCE(NULLIF(file_type, ''), 'pdf'),
                  location_type = COALESCE(NULLIF(location_type, ''), 'page'),
                  location = CASE
                    WHEN location IS NULL OR location = '' THEN CAST(page_number AS TEXT)
                    ELSE location
                  END,
                  extraction_method = COALESCE(NULLIF(extraction_method, ''), 'text'),
                  uploaded_at = COALESCE(uploaded_at, created_at)
                """
            )
        stats["backfilled"] = conn.total_changes
        conn.commit()
        logger.info("migrate_sqlite_done", **{k: v for k, v in stats.items() if k != "path"})
        return stats
    finally:
        conn.close()


def migrate_from_settings() -> dict | None:
    """Migrate the configured app database when it is a local SQLite file."""
    from backend.app.config import get_settings

    settings = get_settings()
    url = settings.database_url or ""
    # sqlite+aiosqlite:///./data/chatbot.db  or  sqlite:///...
    if "sqlite" not in url:
        return None
    # Strip SQLAlchemy prefix
    raw = url.split(":///", 1)[-1] if ":///" in url else url.split("://", 1)[-1]
    if raw in {":memory:", ""} or raw.startswith("file:"):
        return None
    path = Path(raw)
    if not path.is_absolute():
        from backend.app.config import BASE_DIR

        path = BASE_DIR / path
    if not path.is_file():
        return None
    return migrate_sqlite_file(path)
