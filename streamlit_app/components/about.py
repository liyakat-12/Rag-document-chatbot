"""About DocuMind AI."""

from __future__ import annotations

import streamlit as st


def render_about() -> None:
    st.markdown("## About DocuMind AI")
    st.markdown(
        """
**Ask your documents. Get grounded answers.**

DocuMind AI is a retrieval-augmented generation (RAG) assistant for private PDFs.
It retrieves evidence with hybrid search, then answers only from that evidence.

### How retrieval works
1. **Semantic (FAISS)** — embedding similarity for paraphrased questions  
2. **Keyword (BM25)** — lexical matches for exact terms  
3. **RRF fusion** — combines both rankings into one grounded context set  

### Grounding policy
If the retrieved context is insufficient, DocuMind responds:

> I couldn't find that information in the uploaded documents.

It will not invent citations or unsupported facts.

### Privacy
Documents and chat history stay on your machine (local uploads, SQLite, FAISS).
Configure cloud LLM providers only when you intentionally enable them in `.env`.
"""
    )
