# RAG Document Chatbot

Production-ready **Retrieval-Augmented Generation (RAG)** chatbot. Upload PDFs, ask questions, and get grounded answers with source citations, confidence scores, and streaming responses.

---

## Features

| Core | UX | Bonus |
|------|----|-------|
| Multi-PDF upload & indexing | Dark mode | Hybrid search (BM25 + FAISS) |
| Chunking + OpenAI embeddings | Drag-and-drop upload | Metadata filtering |
| FAISS vector store | Typing animation | Semantic caching |
| RetrievalQA with grounded prompts | Streaming answers | Token counting |
| Chat memory & multi-session | Markdown rendering | Conversation summarization |
| Source citations | Copy answer | Document statistics |
| Confidence score | Download chat as PDF | Admin dashboard |
| Delete / re-index documents | Rate answers (👍/👎) | Configurable LLM provider |

---

## Architecture

```
PDF → Extract → Clean → Chunk → Embed → FAISS
                                           ↓
Question → Hybrid Retriever (BM25 + Vector) → LLM → Answer + Sources
```

**Never hallucinates:** if context is insufficient, the model responds exactly:

> I couldn't find that information in the uploaded documents.

---

## Project Structure

```
rag-document-chatbot/
├── backend/app/       # FastAPI + RAG pipeline
├── streamlit_app/     # Streamlit UI (primary frontend)
├── frontend/          # Legacy React UI (optional, not required)
├── tests/
├── uploads/
├── vector_store/
├── data/
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Requirements

- Python **3.12 or 3.13** (recommended: 3.12)
- OpenAI API key (or Azure OpenAI / Anthropic + OpenAI embeddings)
- No Node.js required (Streamlit UI)

---

## Setup

### 1. Clone & environment

```bash
cd RAG_Document_Chatbot
copy .env.example .env   # Windows
# cp .env.example .env   # macOS/Linux
```

Edit `.env` and set at least:

```env
OPENAI_API_KEY=sk-your-key-here
LLM_PROVIDER=openai
MAX_UPLOAD_SIZE_MB=40
```

### 2. Backend

```bash
# Prefer Python 3.12
py -3.12 -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
# python3.12 -m venv .venv && source .venv/bin/activate

pip install -r requirements.txt
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Or double-click `run_backend.bat` on Windows.

API docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 3. Streamlit UI

```bash
# From project root, with venv activated:
streamlit run streamlit_app/app.py --server.port 8501
```

Or double-click `run_frontend.bat`.

UI: [http://localhost:8501](http://localhost:8501)

### 4. Docker (optional)

```bash
docker compose up --build
```

- Backend: `http://localhost:8000`
- Streamlit: `http://localhost:8501`

---

## Deploying to Streamlit Community Cloud (free)

Streamlit Community Cloud only runs a single process on a single exposed
port, so `streamlit_app/app.py` automatically boots the FastAPI backend
in-process (see `streamlit_app/backend_runtime.py`) if nothing is already
listening on port 8000 — no separate backend deployment needed.

1. Push this repo to GitHub (already done if you're reading this from there).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with GitHub.
3. Click **New app** → select this repo → branch `main` → main file path
   `streamlit_app/app.py` → **Deploy**.
4. That's it. With no configuration, it runs fully free/offline
   (`LLM_PROVIDER=extractive`, `EMBEDDING_PROVIDER=local`).
5. Optional: to use a real LLM instead of the offline extractive mode, open
   **App settings → Secrets** and add e.g.:
   ```toml
   LLM_PROVIDER = "openai"
   OPENAI_API_KEY = "sk-..."
   ```

Notes:

- Storage is **ephemeral** — uploaded PDFs, the vector index, and chat
  history reset whenever the app restarts or sleeps (after ~12h idle).
  Fine for demos/portfolios; not for production data.
- Free tier is capped at roughly 1 GB RAM — keep uploaded PDFs modest in
  size and number.
- Hugging Face Spaces is **not** a free option for this app as of mid-2026:
  HF now requires a PRO plan to create compute-backed (Docker/Gradio)
  Spaces on free personal accounts; only static or ZeroGPU Gradio Spaces
  remain free, which don't fit this architecture.

---

## Environment Variables

See [`.env.example`](.env.example) for the full list. Key variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_PROVIDER` | `openai` \| `azure_openai` \| `anthropic` | `openai` |
| `OPENAI_API_KEY` | OpenAI API key | — |
| `OPENAI_CHAT_MODEL` | Chat model | `gpt-4o-mini` |
| `OPENAI_EMBEDDING_MODEL` | Embedding model | `text-embedding-3-small` |
| `MAX_UPLOAD_SIZE_MB` | Upload limit | `40` |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | Splitter settings | `1000` / `200` |
| `DATABASE_URL` | Async SQLAlchemy URL | SQLite file |
| `SEMANTIC_CACHE_ENABLED` | Cache similar queries | `true` |

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/upload` | Upload PDF(s) |
| `POST` | `/api/v1/chat` | Chat (non-streaming, `stream=false`) |
| `POST` | `/api/v1/chat/stream` | Chat (SSE streaming) |
| `GET` | `/api/v1/history` | List chat sessions |
| `GET` | `/api/v1/documents` | List documents |
| `DELETE` | `/api/v1/document/{id}` | Delete a document |
| `POST` | `/api/v1/reindex` | Rebuild vector index |
| `GET` | `/api/v1/admin/stats` | Admin dashboard stats |
| `GET` | `/api/v1/health` | Health check |

---

## How RAG Works

1. **Upload** — PDFs are validated (type, size ≤ 40 MB, magic bytes) and stored under `uploads/`.
2. **Parse** — `PyPDFLoader` extracts page text; text is cleaned.
3. **Chunk** — `RecursiveCharacterTextSplitter` creates overlapping chunks with metadata (`filename`, `page_number`, `chunk_id`).
4. **Embed** — OpenAI embeddings are written to **FAISS**.
5. **Retrieve** — Hybrid search (dense FAISS + BM25) fused with Reciprocal Rank Fusion.
6. **Generate** — LLM answers **only** from retrieved context, with citations and a confidence heuristic.
7. **Memory** — Sessions and messages persist in SQLite; long chats are summarized.

---

## Screenshots

> Place screenshots in `frontend/public/screenshots/` and link them here.

| Light mode | Dark mode |
|------------|-----------|
| ![Chat light](frontend/public/screenshots/chat-light.png) | ![Chat dark](frontend/public/screenshots/chat-dark.png) |

---

## Testing

```bash
pip install -r requirements.txt
pytest -q
```

- `tests/unit/` — sanitization, cleaning, confidence, RRF fusion
- `tests/integration/` — health, history, upload validation, admin stats

---

## Security

- PDF-only uploads with content-type + magic-byte checks
- Filename sanitization (no path traversal)
- Max upload size: **40 MB**
- Secrets loaded from environment (never hardcoded)

---

## Future Improvements

- Multi-user auth (JWT / OAuth)
- Persistent vector DB (pgvector / Qdrant)
- OCR for scanned PDFs
- Evaluations (RAGAS) and answer grounding checks
- Role-based document collections

---

## License

MIT
