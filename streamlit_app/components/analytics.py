"""Analytics dashboard — live metrics + offline evaluation snapshot."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable

import streamlit as st

import components._pathfix  # noqa: F401
from components import friendly_error

_REPO_ROOT = Path(__file__).resolve().parents[2]
_EVAL_REPORT = _REPO_ROOT / "evals" / "last_report.json"


def _lat(block: dict[str, Any] | None, key: str = "p50_ms") -> str:
    if not block:
        return "—"
    val = block.get(key)
    return f"{val} ms" if val is not None else "—"


def _load_eval_report() -> dict[str, Any] | None:
    if not _EVAL_REPORT.is_file():
        return None
    try:
        return json.loads(_EVAL_REPORT.read_text(encoding="utf-8"))
    except Exception:
        return None


def _render_eval_snapshot(report: dict[str, Any] | None) -> None:
    st.markdown("### Offline evaluation")
    st.caption(
        "From `evals/last_report.json` produced by `python -m evals.run_eval`. "
        "Separate from live production counters above."
    )
    if not report:
        st.info(
            "No evaluation report found. From the repo root, run:\n\n"
            "`python -m evals.run_eval`\n\n"
            "Results are written to `evals/last_report.json`."
        )
        return

    generated = report.get("generated_at") or "—"
    dataset = report.get("dataset") or "—"
    local = report.get("local_retrieval") or {}
    n_cases = local.get("n_cases")
    st.caption(f"Generated: {generated} · cases: {n_cases if n_cases is not None else '—'} · source: last_report.json")
    if isinstance(dataset, str) and dataset:
        st.caption(f"Dataset: `{Path(dataset).name}`")

    if local.get("skipped"):
        st.warning("Local retrieval section was skipped in the last report.")
        return

    hit = local.get("keyword_hit_rate")
    lat = local.get("latency_ms") or {}
    notes = local.get("metric_notes") or {}

    m = st.columns(2)
    m[0].metric(
        "Keyword hit rate",
        f"{hit * 100:.0f}%" if isinstance(hit, (int, float)) else "—",
        help=notes.get("keyword_hit_rate") or "Proxy relevance metric",
    )
    m[1].metric("Median latency", f"{lat.get('p50')} ms" if lat.get("p50") is not None else "—")

    m2 = st.columns(2)
    m2[0].metric("Avg latency", f"{lat.get('avg')} ms" if lat.get("avg") is not None else "—")
    m2[1].metric("p95 latency", f"{lat.get('p95')} ms" if lat.get("p95") is not None else "—")

    # Honest unavailable metrics — do not invent Recall@K / MRR
    recall_note = notes.get("Recall@K") or "unavailable"
    mrr_note = notes.get("MRR") or "unavailable"
    st.caption(f"Recall@K: {recall_note}")
    st.caption(f"MRR: {mrr_note}")

    if local.get("not_found_message"):
        st.caption(f"Not-found message under test: “{local.get('not_found_message')}”")
    if local.get("followup_expansion_ok") is not None:
        st.caption(
            "Follow-up query expansion: "
            + ("ok" if local.get("followup_expansion_ok") else "failed")
        )


def render_analytics(client_factory: Callable) -> None:
    st.markdown('<p class="page-kicker">Operations</p>', unsafe_allow_html=True)
    st.markdown("## Analytics")
    st.caption("Live process metrics and the latest offline evaluation snapshot — no demo placeholders.")

    c_refresh, _ = st.columns([1, 3])
    with c_refresh:
        if st.button("Refresh", use_container_width=True):
            st.rerun()

    st.markdown("### Live production")
    if not st.session_state.get("backend_ok"):
        st.warning("Backend unavailable — live metrics require the API.")
    else:
        try:
            stats = client_factory().admin_stats()
            health = client_factory().health()
        except Exception as exc:
            st.error(friendly_error(exc))
            stats = None
            health = None

        if stats is not None:
            docs = stats.get("documents") or {}
            hits = int(stats.get("cache_hits") or 0)
            misses = int(stats.get("cache_misses") or 0)
            total_cache = hits + misses
            hit_rate = f"{(hits / total_cache * 100):.0f}%" if total_cache else "—"

            m = st.columns(2)
            m[0].metric("Docs indexed", docs.get("indexed_documents", 0))
            m[1].metric("Conversations", stats.get("total_sessions", 0))
            m = st.columns(2)
            m[0].metric("Answers", stats.get("questions_answered", 0))
            m[1].metric("Cache hit rate", hit_rate, help=f"{hits} hits / {misses} misses")

            m2 = st.columns(2)
            m2[0].metric("Pages", docs.get("total_pages", 0))
            m2[1].metric("Chunks", docs.get("total_chunks", 0))
            m2 = st.columns(2)
            m2[0].metric("Feedback ↑", stats.get("feedback_up", 0))
            m2[1].metric("Feedback ↓", stats.get("feedback_down", 0))

            latency = stats.get("latency") or {}
            st.markdown("#### Latency (rolling window)")
            st.caption(latency.get("note") or "Samples since backend start.")
            L = st.columns(2)
            L[0].metric("Total p50", _lat(latency.get("total")))
            L[1].metric("Retrieval p50", _lat(latency.get("retrieval")))
            L = st.columns(2)
            L[0].metric("Generation p50", _lat(latency.get("generation")))
            L[1].metric("Cache lookup p50", _lat(latency.get("cache_lookup")))

            L2 = st.columns(2)
            L2[0].metric("Total p95", _lat(latency.get("total"), "p95_ms"))
            L2[1].metric("FAISS p50", _lat(latency.get("faiss")))
            L2 = st.columns(2)
            L2[0].metric("BM25 p50", _lat(latency.get("bm25")))
            L2[1].metric("Samples", (latency.get("total") or {}).get("count") or 0)

            if health:
                st.success(
                    f"API healthy · {health.get('app')} · "
                    f"LLM `{health.get('llm_provider')}` · "
                    f"embeddings `{health.get('embedding_provider', '—')}` · "
                    f"retrieval `{health.get('retrieval_strategy', 'hybrid_rrf')}`"
                )

    st.divider()
    _render_eval_snapshot(_load_eval_report())
