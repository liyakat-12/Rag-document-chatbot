"""Isolated evaluation FAISS + BM25 index built from the primary corpus (real/).

Never reads or writes the app's live vector_store/ or SQLite database.
Reuses backend ingest/embedding modules; keeps a separate on-disk cache under
evals/.index/<corpus_hash>_<chunking_config_hash>/.

Default corpus subset is ``primary`` (evals/corpus/real/). Synthetic fixtures
under evals/corpus/synthetic/ are reserved for the Phase 4 CI fixture.
"""

from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import faiss
from langchain_community.docstore.in_memory import InMemoryDocstore
from langchain_community.vectorstores import FAISS
from langchain_core.documents import Document as LCDocument
from rank_bm25 import BM25Okapi

from evals.corpus_util import CorpusSubset, corpus_hash, list_corpus_files
from evals.span_map import RetrievedChunk

EVALS_DIR = Path(__file__).resolve().parent
INDEX_ROOT = EVALS_DIR / ".index"


def chunking_config_hash(config: dict[str, Any]) -> str:
    """Stable hash of chunking + embedding + ingest-quality settings that affect the index.

    Enabling ``ingest_strip_repeated_headers_footers`` or ``ingest_flag_low_text_pages``
    changes this hash so eval indexes land in a separate directory under evals/.index/.
    """
    payload = {
        "chunk_size": int(config.get("chunk_size", 1000)),
        "chunk_overlap": int(config.get("chunk_overlap", 200)),
        "embedding_provider": str(config.get("embedding_provider", "local")),
        "embedding_model": str(
            config.get("embedding_model")
            or config.get("local_embedding_model")
            or "BAAI/bge-small-en-v1.5"
        ),
    }
    # Only fold ingest-quality flags into the hash when enabled so the default
    # index directory (flags off) stays stable; enabled flags get a new dir.
    strip_h = bool(config.get("ingest_strip_repeated_headers_footers", False))
    flag_lt = bool(config.get("ingest_flag_low_text_pages", False))
    if strip_h or flag_lt:
        payload["ingest_strip_repeated_headers_footers"] = strip_h
        payload["ingest_flag_low_text_pages"] = flag_lt
        payload["ingest_low_text_char_threshold"] = int(
            config.get("ingest_low_text_char_threshold", 100)
        )
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def index_dir_for(corpus_h: str, chunk_h: str) -> Path:
    return INDEX_ROOT / f"{corpus_h[:16]}_{chunk_h}"


@dataclass
class EvalIndex:
    store: FAISS
    bm25: BM25Okapi | None
    bm25_docs: list[LCDocument]
    path: Path
    corpus_hash: str
    chunking_config_hash: str
    n_chunks: int


def _tokenize(text: str) -> list[str]:
    return [t.lower() for t in text.split() if t.strip()]


def _l2_to_similarity(distance: float) -> float:
    return 1.0 / (1.0 + max(0.0, float(distance)))


def _build_chunks(
    config: dict[str, Any],
    *,
    subset: CorpusSubset = "primary",
) -> list[LCDocument]:
    """Extract + chunk every primary (or selected) corpus PDF."""
    from backend.app.config import get_settings
    from backend.app.rag.ingest import load_pdf, split_documents

    settings = get_settings()
    # Temporarily apply eval chunking if provided (settings object is cached —
    # mutate only for this build via local splitter params inside split_documents
    # which reads get_settings(). Override by monkeypatching attributes for the call.)
    old_size, old_overlap = settings.chunk_size, settings.chunk_overlap
    try:
        settings.chunk_size = int(config.get("chunk_size", old_size))
        settings.chunk_overlap = int(config.get("chunk_overlap", old_overlap))
        all_chunks: list[LCDocument] = []
        strip_h = bool(config.get("ingest_strip_repeated_headers_footers", False))
        flag_lt = bool(config.get("ingest_flag_low_text_pages", False))
        lt_thr = int(config.get("ingest_low_text_char_threshold", 100))
        for pdf in list_corpus_files(subset=subset):
            if pdf.suffix.lower() != ".pdf":
                continue
            pages = load_pdf(
                pdf,
                strip_headers=strip_h,
                flag_low_text=flag_lt,
                low_text_threshold=lt_thr,
            )
            if not pages:
                continue
            doc_id = str(uuid4())
            chunks = split_documents(pages, document_id=doc_id, filename=pdf.name)
            all_chunks.extend(chunks)
        return all_chunks
    finally:
        settings.chunk_size = old_size
        settings.chunk_overlap = old_overlap


def _empty_faiss() -> FAISS:
    from backend.app.rag.llm_factory import get_shared_embeddings

    embeddings = get_shared_embeddings()
    dim = len(embeddings.embed_query("dimension probe"))
    index = faiss.IndexFlatL2(dim)
    return FAISS(
        embedding_function=embeddings,
        index=index,
        docstore=InMemoryDocstore({}),
        index_to_docstore_id={},
    )


def _save_index(store: FAISS, path: Path, meta: dict[str, Any]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    store.save_local(str(path / "faiss"))
    (path / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")


def _load_index(path: Path) -> FAISS | None:
    from backend.app.rag.llm_factory import get_shared_embeddings

    faiss_dir = path / "faiss"
    if not (faiss_dir / "index.faiss").exists():
        return None
    embeddings = get_shared_embeddings()
    return FAISS.load_local(
        str(faiss_dir),
        embeddings,
        allow_dangerous_deserialization=True,
    )


def build_or_load_eval_index(
    config: dict[str, Any],
    *,
    subset: CorpusSubset = "primary",
) -> EvalIndex:
    """
    Return an EvalIndex for the current primary corpus + chunking config.

    Rebuilds when corpus_hash or chunking_config_hash change.
    Default subset is ``primary`` (real PDFs only).
    """
    c_hash = corpus_hash(subset=subset)
    ch_hash = chunking_config_hash(config)
    path = index_dir_for(c_hash, ch_hash)
    meta_path = path / "meta.json"

    store: FAISS | None = None
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            if (
                meta.get("corpus_hash") == c_hash
                and meta.get("chunking_config_hash") == ch_hash
                and meta.get("corpus_subset", "primary") == subset
            ):
                store = _load_index(path)
        except Exception:
            store = None

    if store is None:
        INDEX_ROOT.mkdir(parents=True, exist_ok=True)
        chunks = _build_chunks(config, subset=subset)
        store = _empty_faiss()
        if chunks:
            store.add_documents(chunks)
        meta = {
            "corpus_hash": c_hash,
            "chunking_config_hash": ch_hash,
            "corpus_subset": subset,
            "n_chunks": len(chunks),
            "n_files": len(list_corpus_files(subset=subset)),
            "config_slice": {
                "chunk_size": config.get("chunk_size"),
                "chunk_overlap": config.get("chunk_overlap"),
                "embedding_provider": config.get("embedding_provider"),
            },
        }
        _save_index(store, path, meta)
    else:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))

    docs = list(store.docstore._dict.values())  # type: ignore[attr-defined]
    tokens = [_tokenize(d.page_content) for d in docs]
    bm25 = BM25Okapi(tokens) if tokens else None
    return EvalIndex(
        store=store,
        bm25=bm25,
        bm25_docs=docs,
        path=path,
        corpus_hash=c_hash,
        chunking_config_hash=ch_hash,
        n_chunks=len(docs),
    )


def _dense_search(index: EvalIndex, query: str, k: int) -> list[tuple[LCDocument, float]]:
    if index.n_chunks == 0:
        return []
    raw = index.store.similarity_search_with_score(query, k=k)
    return [(doc, _l2_to_similarity(score)) for doc, score in raw]


def _sparse_search(index: EvalIndex, query: str, k: int) -> list[tuple[LCDocument, float]]:
    if index.bm25 is None or not index.bm25_docs:
        return []
    scores = index.bm25.get_scores(_tokenize(query))
    ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)
    out: list[tuple[LCDocument, float]] = []
    for idx, score in ranked:
        if score <= 0:
            continue
        out.append((index.bm25_docs[idx], float(score)))
        if len(out) >= k:
            break
    return out


@dataclass
class EvalSearchResult:
    results: list[tuple[LCDocument, float]]
    details: dict[str, Any]


def search_eval_index(
    index: EvalIndex,
    query: str,
    *,
    top_k: int = 4,
    dense_weight: float = 0.5,
    dense_floor: float = 0.22,
) -> EvalSearchResult:
    """Hybrid RRF search against the isolated eval index only."""
    from backend.app.rag.hybrid_search import reciprocal_rank_fusion

    fetch_k = max(top_k * 2, 8)
    dense_w = min(1.0, max(0.0, float(dense_weight)))
    sparse_w = 1.0 - dense_w
    t0 = time.perf_counter()
    dense_ms = 0.0
    sparse_ms = 0.0

    def _d() -> list[tuple[LCDocument, float]]:
        nonlocal dense_ms
        t = time.perf_counter()
        out = _dense_search(index, query, fetch_k)
        dense_ms = (time.perf_counter() - t) * 1000
        return out

    def _s() -> list[tuple[LCDocument, float]]:
        nonlocal sparse_ms
        t = time.perf_counter()
        out = _sparse_search(index, query, fetch_k)
        sparse_ms = (time.perf_counter() - t) * 1000
        return out

    with ThreadPoolExecutor(max_workers=2) as pool:
        dense = pool.submit(_d).result()
        sparse = pool.submit(_s).result()

    dense = [(d, s) for d, s in dense if s >= dense_floor]
    sparse = [(d, s) for d, s in sparse if s > 0.0]
    fused = reciprocal_rank_fusion([dense, sparse], weights=[dense_w, sparse_w]) if (dense or sparse) else []

    seen: set[str] = set()
    deduped: list[tuple[LCDocument, float]] = []
    for doc, score in fused:
        key = str(doc.metadata.get("chunk_id") or id(doc))
        if key in seen:
            continue
        seen.add(key)
        deduped.append((doc, score))
        if len(deduped) >= top_k:
            break

    if deduped:
        mx = max(s for _, s in deduped) or 1.0
        normalized = [(d, s / mx) for d, s in deduped]
    else:
        normalized = []

    total_ms = (time.perf_counter() - t0) * 1000
    return EvalSearchResult(
        results=normalized,
        details={
            "strategy": "hybrid_rrf_eval_index",
            "top_k": top_k,
            "latency_ms": round(total_ms, 2),
            "faiss_ms": round(dense_ms, 2),
            "bm25_ms": round(sparse_ms, 2),
            "n_chunks_indexed": index.n_chunks,
            "index_path": str(index.path),
        },
    )


def as_retrieved(results: list[tuple[LCDocument, float]]) -> list[RetrievedChunk]:
    return [RetrievedChunk.from_langchain(doc) for doc, _ in results]
