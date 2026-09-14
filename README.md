# DocuMind AI

**Ask your documents. Get grounded answers.**

Enterprise-style **Retrieval-Augmented Generation (RAG)** assistant for private PDFs.
Upload documents, ask questions, and receive answers with source citations, grounding confidence, and hybrid retrieval diagnostics.

---

## Problem

Teams need trustworthy answers from their own PDFs — resumes, policies, manuals — without sending everything to a black-box chatbot that invents facts.

## Solution

DocuMind AI indexes your PDFs locally, retrieves evidence with **FAISS + BM25 → RRF fusion**, then answers only from that context. If evidence is missing, it says so.

---

## Features

- Multi-PDF upload (40 MB) with real ingestion stage timings
- Hybrid retrieval (semantic + keyword) with expandable retrieval details
- Grounded answers, citations, heuristic grounding confidence
- Streaming chat, conversation history, follow-up query expansion
- Semantic cache, thumbs feedback, PDF conversation export
- Documents / Analytics / Settings / About UI
- Light & dark enterprise themes
- Offline **extractive** mode + local FastEmbed embeddings
- Optional OpenAI / Azure OpenAI / Anthropic LLMs
- Docker Compose, tests, and an evaluation harness

---

## Architecture

```
                ┌─────────────────┐
                │   PDF Upload    │
                └────────┬────────┘
                         ↓
                ┌─────────────────┐
                │ Text Extraction │
                └────────┬────────┘
                         ↓
                ┌─────────────────┐
                │    Chunking     │
                └────────┬────────┘
                         ↓
                ┌─────────────────┐
                │   Embeddings    │
                └────────┬────────┘
                         ↓
                ┌─────────────────────┐
                │ FAISS + BM25 Index  │
                └──────────┬──────────┘
                           │
Question ───────────────→ Retrieval
                           ↓
                    Hybrid Fusion (RRF)
                           ↓
                    Context Builder
                           ↓
                         LLM / Extractive
                           ↓
                Answer + Citations
```

### Hybrid retrieval

1. **Semantic (FAISS)** — finds paraphrased / meaning-similar chunks  
2. **Keyword (BM25)** — finds exact lexical matches  
3. **RRF fusion** — combines rankings (`HYBRID_SEARCH_WEIGHT` = dense weight)

---

## Technology stack

| Layer | Tech |
|-------|------|
| UI | Streamlit |
| API | FastAPI + Uvicorn + SSE |
| RAG | LangChain |
| Vectors | FAISS (`IndexFlatL2`) |
| Keywords | rank-bm25 |
| Embeddings | FastEmbed (`BAAI/bge-small-en-v1.5`) or OpenAI |
| PDF | pypdf |
| DB | SQLite + SQLAlchemy + aiosqlite |

---

## Project structure

```
RAG_Document_Chatbot/
├── backend/app/          # FastAPI + RAG pipeline
│   ├── api/              # documents, chat, admin
│   ├── rag/              # ingest, FAISS, BM25, QA, LLM factory
│   ├── services/         # orchestration
│   └── db/               # SQLAlchemy models
├── streamlit_app/        # DocuMind AI UI
│   ├── components/       # chat, documents, analytics, …
│   └── styles/           # light/dark themes
├── evals/                # retrieval / groundedness evaluation
├── tests/
├── uploads/ · vector_store/ · data/
├── docker-compose.yml
└── requirements.txt
```

---

## Installation

```bash
cd RAG_Document_Chatbot
copy .env.example .env          # Windows
# cp .env.example .env          # macOS/Linux

py -3.12 -m venv .venv
.venv\Scripts\activate          # Windows
# source .venv/bin/activate     # macOS/Linux

pip install -r requirements.txt
```

Default `.env` uses **extractive** LLM + **local** embeddings (no paid API required).

---

## Configuration

See `.env.example`. Important keys:

| Variable | Meaning |
|----------|---------|
| `LLM_PROVIDER` | `extractive` · `openai` · `azure_openai` · `anthropic` |
| `EMBEDDING_PROVIDER` | `local` · `openai` |
| `RETRIEVER_TOP_K` | Fused chunks returned |
| `HYBRID_SEARCH_WEIGHT` | Dense weight in RRF |
| `MAX_UPLOAD_SIZE_MB` | Default 40 |

Never commit `.env` or API keys.

---

## Running locally

**Backend**

```bash
uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

API docs: http://localhost:8000/docs

**UI**

```bash
streamlit run streamlit_app/app.py --server.port 8501
```

UI: http://localhost:8501

Or use `run_backend.bat` / `run_frontend.bat` on Windows.

---

## Docker

```bash
docker compose up --build -d
```

- UI: http://localhost:8501  
- API: http://localhost:8000  

Data persists in Docker volumes (`uploads`, `vector_store`, `data`).

---

## Deploy

### Option A — Streamlit Community Cloud (easiest public URL)

Your app already boots FastAPI **in-process** via `streamlit_app/backend_runtime.py`, so one Streamlit service is enough.

1. Push this repo to GitHub (exclude `.env` — already gitignored).
2. Go to [share.streamlit.io](https://share.streamlit.io) → **New app**.
3. Select repo `liyakat-12/Rag-document-chatbot`, branch `main`.
4. Main file path: `streamlit_app/app.py`
5. Python version: **3.12**
6. In **Advanced settings → Secrets**, paste values from `streamlit_app/.streamlit/secrets.toml.example` and set your real `OPENAI_API_KEY` (or use `LLM_PROVIDER = "extractive"` with no key).
7. Deploy.

Notes:
- Free Cloud has limited CPU/RAM; local FastEmbed may be slow on first run.
- Uploaded docs on Cloud are ephemeral unless you add external storage later.

### Option B — Docker on a VPS (DigitalOcean / AWS / Azure VM)

1. Install Docker + Compose on the server.
2. Copy the project (or `git clone`) and create `.env` from `.env.example`.
3. Run:

```bash
docker compose up --build -d
```

4. Open firewall ports **8501** (UI) and optionally **8000** (API).
5. Point a domain / reverse proxy (Nginx/Caddy) at port 8501.

### Option C — Hugging Face Spaces (good public demo)

**Yes — HF is a solid choice** for this app (better than Vercel).

1. Push the repo to GitHub.
2. Create a Space: [huggingface.co/new-space](https://huggingface.co/new-space)
   - SDK: **Docker**
   - Connect your GitHub repo
3. Space reads the root `Dockerfile` (Streamlit on port **7860**, API in-process).
4. Optional: copy Space card text from `README_HF.md` into the Space README.
5. Add secrets under **Settings → Variables and secrets** (see `README_HF.md`).

UI URL will look like: `https://huggingface.co/spaces/<you>/documind-ai`

---

### Option D — Keep running locally

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
streamlit run streamlit_app/app.py --server.port 8501
```

---

## Example usage

1. Open **Documents** → upload a PDF → confirm pipeline stages → **Document ready**  
2. Open **Chat** → try a suggested question  
3. Inspect **Sources**, **Grounding confidence**, and optional **Retrieval details**  
4. Rate answers; export the conversation as PDF  

---

## Evaluation

```bash
python -m evals.run_eval           # local retrieval checks (needs indexed docs)
python -m evals.run_eval --api     # live chat groundedness checks
```

Dataset: `evals/dataset.json`. Scores are measured, not fabricated.

---

## Testing

```bash
pytest -q
```

---

## Limitations

- Extractive mode returns grounded snippets, not fluent generative prose  
- Confidence is a **heuristic** from retrieval scores, not a calibrated probability  
- BM25 lives in memory and is rebuilt after index changes  
- No built-in multi-user authentication on the API  

---

## Future improvements

- Auth / multi-tenant workspaces  
- Persistent BM25 + async ingest progress SSE  
- Stronger query rewriting for follow-ups  
- Richer evaluation (RAGAS / human labels)  

---

## License

Use and modify for your projects. Keep secrets out of git.
