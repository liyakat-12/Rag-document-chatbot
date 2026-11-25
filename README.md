# DocuMind AI

**Ask your documents. Get grounded answers.**

Private document question-answering with **hybrid retrieval** (FAISS + BM25 → Reciprocal Rank Fusion), citations, offline extractive answering, and measurable latency instrumentation. Optional advanced retrieval adds multi-query rewriting and cross-encoder reranking.

---

## Problem

Teams need trustworthy answers from their own PDFs — resumes, policies, manuals — without inventing facts or mixing evidence across unrelated files.

## Solution

DocuMind indexes PDFs locally, retrieves evidence with dense + sparse search fused by RRF, then answers only from that context. If evidence is missing, it says so. External LLMs are optional; **extractive mode works fully offline**.

---

## Architecture

```
PDF upload → extract → chunk (+ page metadata)
        → FastEmbed (local) → FAISS
        → BM25 index
Question → (optional semantic cache)
        → (optional) original + rewritten search queries
        → parallel FAISS + BM25 per query → RRF fusion
        → (optional) cross-encoder reranking → top-k context
        → Extractive / OpenAI / Azure / Anthropic
        → Answer + citations + retrieval-strength score + timings
```

| Layer | Choice |
|-------|--------|
| API | FastAPI |
| UI | Streamlit |
| Embeddings | FastEmbed `BAAI/bge-small-en-v1.5` (default) |
| Vectors | FAISS (L2 → similarity) |
| Sparse | BM25 (`rank_bm25`) |
| Fusion | Weighted Reciprocal Rank Fusion |
| LLM | `extractive` (default) · OpenAI · Azure · Anthropic |
| DB | SQLite (documents, chats, semantic cache) |

---

## Features

- Multi-PDF upload with stage timings (extract → chunk → embed → BM25)
- **Search in** document scope (enforced in retrieval + cache keys)
- Hybrid diagnostics expandable under each answer
- Optional multi-query rewriting to improve candidate recall
- Optional cross-encoder reranking over the merged candidate pool
- Streaming chat with citations and copy/export
- Semantic cache scoped by documents + answering mode
- Analytics: cache hit rate + rolling latency p50/p95
- Offline extractive answers; optional cloud synthesis
- Eval harness: `python -m evals.run_eval`

---

## Advanced retrieval (opt-in)

The default release configuration stays unchanged. You can enable the advanced retrieval stages in your local `.env`:

```env
# Query rewriting: original question + up to two alternative search queries
RETRIEVAL_MULTI_QUERY_ENABLED=true
RETRIEVAL_MULTI_QUERY_MAX_VARIANTS=3
RETRIEVAL_MULTI_QUERY_CANDIDATE_MULTIPLIER=4

# Cross-encoder reranking of the merged candidate pool
RETRIEVAL_RERANKER_ENABLED=true
RETRIEVAL_RERANKER_TOP_N=16
RETRIEVAL_RERANKER_MODEL=cross-encoder/ms-marco-MiniLM-L-6-v2
```

Install the optional local reranker dependency:

```bash
pip install -r requirements-optional.txt
```

The original question is always searched. With a generative LLM provider configured, the rewriter proposes bounded alternative phrasings; in offline `extractive` mode it uses a conservative keyword-focused fallback instead. Results from each query are deduplicated and combined with Reciprocal Rank Fusion, then the existing cross-encoder reranker is applied once to the merged candidates. If the reranker dependency or model is unavailable, retrieval falls back to the RRF order.

The cross-encoder model is downloaded on first use and cached locally, so the first request can take longer. Reranking can improve evidence ordering; it cannot correct poor source documents or guarantee a correct answer. The rewrite/reranker settings are included in semantic-cache mode keys so old cached answers are not reused across retrieval configurations.

Both features default to **off** to preserve the existing release-1 behaviour and evaluation baseline. The active settings are visible through `GET /api/v1/admin/system` and retrieval diagnostics returned with chat responses.

---

## Quick start

**Requirements:** Python 3.11+ (3.11 or 3.12), Windows/macOS/Linux.

```bash
# From repo root
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
# source .venv/bin/activate

pip install -r requirements.txt
copy .env.example .env   # or: cp .env.example .env
```

### Ports (important)

Another app often occupies **8000** on this machine. DocuMind prefers:

| Service | Default |
|---------|---------|
| Backend API | **8001** if 8000 is busy (`run_backend.bat` auto-selects) |
| Streamlit UI | **8501** |

```bash
# Terminal 1 — API
uvicorn backend.app.main:app --host 127.0.0.1 --port 8001

# Terminal 2 — UI
streamlit run streamlit_app/app.py --server.port 8501
```

**Windows one-command:** double-click `run_documind.bat` — starts backend + UI, skips services that are already healthy, writes `.uvicorn_*.log` / `.streamlit_*.log`. Existing `run_backend.bat` and `run_frontend.bat` still work for separate terminals.

- API docs: http://127.0.0.1:8001/docs  
- Health: http://127.0.0.1:8001/api/v1/health  
- Ready: http://127.0.0.1:8001/api/v1/ready  
- UI: http://127.0.0.1:8501  

The Streamlit app **refuses** to attach to a non-DocuMind process on the same port. Sidebar health shows Connected / Checking / Unavailable from a live `/health` probe (short TTL, refreshable).

### Default configuration

```env
LLM_PROVIDER=extractive
EMBEDDING_PROVIDER=local
```

For OpenAI synthesis (sends retrieved context to OpenAI):

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

Never commit `.env`.

---

## Evaluation

```bash
python -m evals.run_eval
python -m evals.run_eval --api --base http://127.0.0.1:8001/api/v1 --out evals/last_report.json
```

**Metric honesty**

| Metric | Status |
|--------|--------|
| Keyword hit rate on retrieved text | Measured when index has content |
| Retrieval latency p50/p95 | Measured |
| Recall@K / MRR | Marked **unavailable** unless gold chunk IDs exist |
| Cache hit rate | From live admin stats |

Do not invent Recall@K numbers for resumes.

---

## Testing

```bash
pytest tests/unit -q
```

---

## API sketch

```http
GET  /api/v1/health
GET  /api/v1/ready
POST /api/v1/upload
GET  /api/v1/documents
POST /api/v1/chat          # { "message", "session_id?", "document_ids?", "stream": false }
POST /api/v1/chat/stream
GET  /api/v1/admin/stats   # includes latency window
```

---

## Privacy & security

- Uploads and vector indexes stay under `uploads/` and `vector_store/` (gitignored).
- API keys stay on the backend; UI never displays secrets.
- External LLM mode is labeled in the UI.
- Delete document removes vectors, file, and clears semantic cache.

---

## Limitations

- Extractive mode quotes passages; it does not rewrite like a chat LLM.
- Scanned PDFs without text layer are not OCR’d.
- Retrieval-strength % is a heuristic, not calibrated accuracy.
- Latency metrics are in-process (reset on backend restart).
- Single-user / local deployment by default (no multi-tenant auth).

---

## Design trade-offs

1. **Hybrid RRF** — balances paraphrase recall (FAISS) with exact-term precision (BM25).
2. **Local embeddings by default** — predictable cost; no embedding quota failures.
3. **Extractive default** — demos and interviews work without a paid key.
4. **Cache scoped by docs + mode** — correctness over hit rate.
5. **Parallel FAISS+BM25** — cuts wall-clock retrieval when both paths are non-trivial.

---

## Roadmap

- Optional cross-encoder reranker behind a flag + eval delta
- Gold chunk-ID eval set for true Recall@K / MRR
- Optional OCR path for scanned PDFs
- Multi-user auth for shared deployments

---

## Resume bullets (fill measured numbers after you run evals)

- Built a hybrid RAG system (FAISS + BM25 → RRF) with document-scoped retrieval, citation metadata, and offline extractive answering.
- Instrumented end-to-end latency (FAISS / BM25 / generation / total p50–p95) exposed in analytics; parallelized dense+sparse retrieval.
- Hardened semantic cache keys by document scope and answering mode; added regression tests for extractive punctuation matching and cache isolation.
