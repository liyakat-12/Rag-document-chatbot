"""Corpus manifest helpers: hashing and reproducible inventory."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            block = f.read(chunk_size)
            if not block:
                break
            h.update(block)
    return h.hexdigest()


def list_corpus_files(corpus_dir: Path | None = None) -> list[Path]:
    root = corpus_dir or CORPUS_DIR
    if not root.is_dir():
        return []
    files: list[Path] = []
    for p in sorted(root.rglob("*")):
        if p.is_file() and p.name not in {"manifest.json", "README.md", ".gitkeep"}:
            if p.suffix.lower() in {".pdf", ".txt", ".md"}:
                files.append(p)
    return files


def corpus_hash(corpus_dir: Path | None = None) -> str:
    """Stable hash of (relative path, file sha256) pairs."""
    root = corpus_dir or CORPUS_DIR
    files = list_corpus_files(root)
    h = hashlib.sha256()
    for p in files:
        rel = p.relative_to(root).as_posix()
        digest = sha256_file(p)
        h.update(f"{rel}:{digest}\n".encode("utf-8"))
    return h.hexdigest() if files else "empty"


def build_manifest(corpus_dir: Path | None = None) -> dict[str, Any]:
    root = corpus_dir or CORPUS_DIR
    entries = []
    for p in list_corpus_files(root):
        entries.append(
            {
                "path": p.relative_to(root).as_posix(),
                "sha256": sha256_file(p),
                "bytes": p.stat().st_size,
                "origin": "local",
                "license": "unknown — review before publishing",
                "notes": "",
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corpus_hash": corpus_hash(root),
        "file_count": len(entries),
        "files": entries,
    }


def write_manifest(corpus_dir: Path | None = None) -> Path:
    root = corpus_dir or CORPUS_DIR
    root.mkdir(parents=True, exist_ok=True)
    data = build_manifest(root)
    path = root / "manifest.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path
