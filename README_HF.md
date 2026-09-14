---
title: DocuMind AI
emoji: 📄
colorFrom: green
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Ask your documents. Get grounded answers.
---

# DocuMind AI

**Ask your documents. Get grounded answers.**

RAG chatbot with hybrid retrieval (FAISS + BM25 → RRF), Streamlit UI, and FastAPI backend (started in-process on Spaces).

## Deploy on Hugging Face

1. Push this repo to GitHub.
2. Hugging Face → **New Space** → SDK: **Docker** → link this GitHub repo.
3. Hardware: **CPU basic** (or upgrade if slow).
4. **Settings → Variables and secrets** — add:

```toml
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_CHAT_MODEL=gpt-4o-mini
LLM_TEMPERATURE=0.1
EMBEDDING_PROVIDER=local
```

Or use offline mode (no key):

```toml
LLM_PROVIDER=extractive
EMBEDDING_PROVIDER=local
```

5. Wait for the build; open the Space URL.

## Notes

- First boot downloads the local embedding model (can take a few minutes).
- Free Spaces sleep when idle; data may reset after sleep.
- Prefer `EMBEDDING_PROVIDER=local` on Spaces to avoid embedding API cost.
