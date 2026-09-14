"""Settings — provider/model/temperature (read-only from env) + advanced."""

from __future__ import annotations

from typing import Callable

import streamlit as st

import components._pathfix  # noqa: F401
from components import friendly_error


def render_settings(client_factory: Callable, api_base: str) -> None:
    st.markdown("## Settings")
    st.caption("Configured via environment variables (`.env`). Secrets are never shown.")

    try:
        info = client_factory().system_info()
    except Exception as exc:
        st.warning(friendly_error(exc))
        try:
            info = client_factory().health()
        except Exception:
            return

    st.markdown("### Generation")
    g1, g2, g3 = st.columns(3)
    g1.metric("LLM provider", info.get("llm_provider", "—"))
    g2.metric("Model", info.get("openai_chat_model", "—"))
    g3.metric("Temperature", info.get("llm_temperature", "—"))

    st.markdown("### Embeddings & retrieval")
    e1, e2, e3 = st.columns(3)
    e1.metric("Embedding provider", info.get("embedding_provider", "—"))
    e2.metric("Top-K", info.get("retriever_top_k", "—"))
    e3.metric("Strategy", info.get("retrieval_strategy", "hybrid_rrf"))

    st.markdown("### Connection")
    st.code(api_base, language="text")

    with st.expander("Advanced configuration", expanded=False):
        st.markdown(
            f"""
| Setting | Value |
|---------|-------|
| Local embedding model | `{info.get('local_embedding_model')}` |
| Hybrid dense weight | `{info.get('hybrid_search_weight')}` |
| Chunk size / overlap | `{info.get('chunk_size')}` / `{info.get('chunk_overlap')}` |
| Semantic cache | `{"on" if info.get('semantic_cache_enabled') else "off"}` @ `{info.get('semantic_cache_threshold')}` |
| Max upload (MB) | `{info.get('max_upload_size_mb')}` |
| Environment | `{info.get('app_env')}` |
| Version | `{info.get('version')}` |
"""
        )
        st.markdown(
            """
Change providers in `.env`:

- `LLM_PROVIDER` = `openai` · `azure_openai` · `anthropic` · `extractive`
- `LLM_TEMPERATURE` = `0.1` (low for factual QA)
- `OPENAI_CHAT_MODEL` = e.g. `gpt-4o-mini`
- `EMBEDDING_PROVIDER` = `local` or `openai`
- `RETRIEVER_TOP_K`, `HYBRID_SEARCH_WEIGHT`
"""
        )
        st.info("Restart the backend after changing `.env`.")
