"""Content-hash registry so identical PDFs are not indexed twice."""

from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Optional

from backend.app.config import get_settings

_lock = threading.Lock()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _registry_path() -> Path:
    return get_settings().vector_store_path / "content_hashes.json"


def _load() -> dict[str, str]:
    path = _registry_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save(data: dict[str, str]) -> None:
    path = _registry_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def find_document_by_hash(content_hash: str) -> Optional[str]:
    with _lock:
        reg = _load()
        return reg.get(content_hash)


def register_hash(content_hash: str, document_id: str) -> None:
    with _lock:
        reg = _load()
        reg[content_hash] = document_id
        _save(reg)


def unregister_document(document_id: str) -> None:
    with _lock:
        reg = _load()
        doomed = [h for h, d in reg.items() if d == document_id]
        for h in doomed:
            del reg[h]
        if doomed:
            _save(reg)
