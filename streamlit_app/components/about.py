"""About & Architecture — portfolio-accurate product page."""

from __future__ import annotations

import streamlit as st


def render_about() -> None:
    st.markdown('<p class="page-kicker">Product</p>', unsafe_allow_html=True)
    st.markdown("## About DocuMind AI")
    st.markdown(
        """
<div class="hero-wrap" style="text-align:left;padding:1.25rem 1.35rem;">
  <p class="brand-hero" style="text-align:left;margin:0 0 .4rem;">Document intelligence</p>
  <p style="margin:0;font-size:1.05rem;line-height:1.55;color:var(--dm-ink-soft);">
    DocuMind AI is a <strong>document-grounded</strong> question-answering system for private PDFs.
    It retrieves evidence with hybrid search, answers only from that evidence, and shows
    citations you can open and verify — on your machine by default.
  </p>
</div>
""",
        unsafe_allow_html=True,
    )

    st.markdown("### Architecture")
    st.caption("Pipeline as implemented in this repository (not aspirational).")
    st.markdown(
        """
<div class="arch-box">
<code>PDF upload</code>
→ Text extraction
→ Chunking (+ page metadata)
→ <code>FastEmbed</code> embeddings
→ <code>FAISS</code> + <code>BM25</code>
→ <code>RRF</code> fusion
→ Evidence selection
→ Extractive <em>or</em> configured LLM answer
→ Citations<br/><br/>
Alongside: SQLite persistence · semantic cache (scoped by docs + mode) · chat history · PDF export
</div>
""",
        unsafe_allow_html=True,
    )

    st.code(
        "PDF Upload → Extract → Chunk → FastEmbed → FAISS + BM25 → RRF\n"
        "  → Evidence → Extractive / LLM → Answer + Citations\n"
        "  (+ SQLite · semantic cache · chat history)",
        language=None,
    )
    # Editable Mermaid source for docs / portfolio write-ups (also in docs/ARCHITECTURE.md)
    with st.expander("Mermaid source (for documentation)", expanded=False):
        st.code(
            """flowchart LR
  A[PDF Upload] --> B[Text Extraction]
  B --> C[Chunking]
  C --> D[FastEmbed]
  D --> E[FAISS]
  C --> F[BM25]
  E --> G[RRF Fusion]
  F --> G
  G --> H[Evidence Selection]
  H --> I[Extractive / LLM]
  I --> J[Answer + Citations]
  K[(SQLite)] -.-> H
  L[Semantic Cache] -.-> I""",
            language="text",
        )

    st.markdown("### Engineering decisions")
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            """
**Why hybrid retrieval?**  
Dense FAISS catches paraphrases and semantic matches. BM25 catches exact names, IDs, and rare terms. Together they cover both meaning and keywords.

**Why RRF?**  
Reciprocal Rank Fusion merges ranked lists without forcing score calibration across FAISS similarity and BM25. Weighted RRF preserves both rankings into one evidence set.

**Citations**  
Each cited passage maps to a stored chunk with filename and page number from ingestion metadata — not regenerated free-text inventing sources.
"""
        )
    with c2:
        st.markdown(
            """
**Offline extractive mode**  
When `LLM_PROVIDER=extractive`, answers are composed from retrieved passages with no cloud call — useful for demos, privacy, and cost control.

**Semantic cache**  
Similar questions can reuse prior answers. Cache keys include document scope and answering mode so a scoped query cannot return another corpus’s answer. Ingestion/reindex invalidates stale entries.

**External LLM privacy**  
OpenAI / Azure / Anthropic only run when configured. Uploaded PDFs and the FAISS index stay local; only the retrieved context (and question) would leave the machine if a cloud provider is enabled.
"""
        )

    st.markdown("### Grounding policy")
    st.info(
        'If retrieval finds insufficient evidence, DocuMind responds: '
        '"I couldn\'t find that information in the uploaded documents." '
        "It does not invent citations or present unrelated TOC text as an answer. "
        "Short greetings skip retrieval entirely."
    )

    st.markdown("### Stack")
    st.caption(
        "FastAPI · Streamlit · LangChain · FastEmbed · FAISS · BM25 · RRF · SQLite"
    )
