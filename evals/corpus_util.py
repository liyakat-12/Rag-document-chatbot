"""Corpus manifest helpers: hashing and reproducible inventory."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
MANIFEST_PATH = CORPUS_DIR / "manifest.json"

# Known provenance for committed fixtures (source_url may be null for synthetic).
KNOWN_META: dict[str, dict[str, str]] = {
    "policy_leave_entitlement.pdf": {
        "origin": "synthetic_fixture",
        "source_url": "",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Generated leave policy for eval",
    },
    "invoice_fixture_q3.pdf": {
        "origin": "synthetic_fixture",
        "source_url": "",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Generated invoice for eval",
    },
    "api_error_codes.pdf": {
        "origin": "synthetic_fixture",
        "source_url": "",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Generated API error codes for eval",
    },
    "qa_design.pdf": {
        "origin": "synthetic_fixture",
        "source_url": "",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Generated QA design note",
    },
    "smoke_ada2.pdf": {
        "origin": "synthetic_fixture",
        "source_url": "",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Tiny smoke resume",
    },
    "_smoke_perf.pdf": {
        "origin": "synthetic_fixture",
        "source_url": "",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Tiny performance resume",
    },
    "circular_amc_disclosure_2024.pdf": {
        "origin": "synthetic_fixture",
        "source_url": "generated://evals/corpus/_gen_public_fixtures.py",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Synthetic regulatory circular",
    },
    "comparative_note_equity_schemes.pdf": {
        "origin": "synthetic_fixture",
        "source_url": "generated://evals/corpus/_gen_public_fixtures.py",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Long comparative note (no TER numbers)",
    },
}


def _scheme_meta(path_name: str) -> dict[str, str]:
    return {
        "origin": "synthetic_fixture",
        "source_url": "generated://evals/corpus/_gen_public_fixtures.py",
        "license": "CC0-equivalent original fixture (DocuMind)",
        "notes": "Near-identical fund SID for disambiguation questions",
    }


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
    skip = {"manifest.json", "README.md", ".gitkeep", "download_corpus.py", "_gen_public_fixtures.py"}
    files: list[Path] = []
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name in skip:
            continue
        if p.name.startswith("_") and p.suffix.lower() == ".py":
            continue
        if p.suffix.lower() in {".pdf", ".txt", ".md"}:
            files.append(p)
    return files


def corpus_hash(corpus_dir: Path | None = None) -> str:
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
        rel = p.relative_to(root).as_posix()
        meta = KNOWN_META.get(p.name)
        if meta is None and p.name.startswith("scheme_"):
            meta = _scheme_meta(p.name)
        if meta is None:
            meta = {
                "origin": "local",
                "source_url": "",
                "license": "unknown — review before publishing",
                "notes": "Add source_url when known",
            }
        entries.append(
            {
                "path": rel,
                "sha256": sha256_file(p),
                "bytes": p.stat().st_size,
                "origin": meta["origin"],
                "source_url": meta.get("source_url", ""),
                "license": meta["license"],
                "notes": meta.get("notes", ""),
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
