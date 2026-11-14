"""Settings — provider/model/temperature (read-only from env) + advanced."""

from __future__ import annotations

from typing import Callable

import streamlit as st

import components._pathfix  # noqa: F401
from components import friendly_error


def render_settings(client_factory: Callable, api_base: str) -> None:
    st.markdown('<p class="page-kicker">Configuration</p>', unsafe_allow_html=True)
    st.markdown("## Settings")
    st.caption("Values come from `.env`. Secrets are never displayed here.")

    try:
        info = client_factory().system_info()
    except Exception as exc:
        st.warning(friendly_error(exc))
        try:
            info = client_factory().health()
        except Exception:
            return

    provider = info.get("llm_provider", "—")
    st.markdown("### Generation")
    g1, g2, g3 = st.columns(3)
    g1.metric("LLM provider", provider)
    # Avoid implying an external chat model is active in extractive mode
    model_label = "—" if provider == "extractive" else (info.get("openai_chat_model") or "—")
    g2.metric("Model", model_label)
    g3.metric("Temperature", info.get("llm_temperature", "—"))

    st.markdown("### Embeddings & retrieval")
    e1, e2, e3 = st.columns(3)
    e1.metric("Embedding provider", info.get("embedding_provider", "—"))
    e2.metric("Top-K", info.get("retriever_top_k", "—"))
    e3.metric("Strategy", info.get("retrieval_strategy", "hybrid_rrf"))

    st.markdown("### Connection")
    st.code(api_base, language="text")
    status = st.session_state.get("backend_status") or "—"
    st.caption(f"UI status: {status} · provider `{provider}`")
    if st.button("Retry connection", key="settings_health_retry"):
        st.session_state["_force_health_refresh"] = True
        st.rerun()
    try:
        ready = client_factory().health()
        st.caption(
            f"Status: {'ready' if ready.get('ready', True) else 'degraded'} · "
            f"version {ready.get('version', '—')}"
        )
    except Exception:
        st.warning("Backend not reachable from this UI.")

    if provider == "extractive":
        st.info(
            "Offline extractive mode — answers are built from retrieved passages "
            "(no external LLM). Set `LLM_PROVIDER=openai` in `.env` for synthesis."
        )
    else:
        st.info(
            "External LLM providers send retrieved context to the configured API. "
            "Extractive mode keeps answering fully local."
        )

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
