"""Analytics dashboard — live usage metrics + evaluation results browser."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Callable

import streamlit as st

import components._pathfix  # noqa: F401
from components import friendly_error

_REPO_ROOT = Path(__file__).resolve().parents[2]


def _lat(block: dict[str, Any] | None, key: str = "p50_ms") -> str:
    if not block:
        return "—"
    val = block.get(key)
    return f"{val} ms" if val is not None else "—"


def _fmt_metric(val: Any) -> str:
    if val is None:
        return "—"
    if isinstance(val, float):
        if 0 <= val <= 1:
            return f"{val:.3f}"
        return f"{val:.2f}"
    return str(val)


def _render_eval_results() -> None:
    from evals.results_browser import (
        empty_state_message,
        latest_ablation,
        latest_eval_run,
        list_eval_runs,
    )

    st.markdown("### Evaluation results")
    st.caption(
        "Offline eval reports from `evals/results/`. "
        "Separate from live usage metrics above. "
        "Draft-label runs show a warning — not for headline claims."
    )

    results_dir = _REPO_ROOT / "evals" / "results"
    c1, c2, c3 = st.columns(3)
    with c1:
        use_filter = st.checkbox("Filter by date", value=False, key="eval_date_filter")
    after = before = None
    if use_filter:
        with c2:
            after = st.date_input(
                "From",
                value=date.today() - timedelta(days=30),
                key="eval_from",
            )
        with c3:
            before = st.date_input("To", value=date.today(), key="eval_to")

    runs = list_eval_runs(results_dir, after=after if use_filter else None, before=before if use_filter else None)
    if not runs:
        st.info(empty_state_message())
        return

    latest = latest_eval_run(results_dir)
    abl = latest_ablation(results_dir)

    if latest:
        st.markdown("#### Latest run")
        if latest.is_draft:
            st.warning("**draft labels** — metrics are not verified; do not use as headline numbers.")
        m = st.columns(4)
        m[0].metric("Split", latest.split or "—")
        m[1].metric("Commit", latest.git_commit or "—")
        m[2].metric("human_verified", latest.n_human_verified)
        m[3].metric("Generated", (latest.generated_at or "—")[:19])
        st.caption(f"File: `{latest.path.name}`")

        rows = latest.metric_rows()
        # Refusal + citation emphasis
        refusal_keys = {
            "not_found_accuracy",
            "refusal_precision",
            "refusal_recall",
            "false_refusal_rate",
        }
        cite_keys = {"citation_precision", "citation_recall", "valid_citation_share"}
        st.markdown("##### Metrics (each shows human_verified count)")
        for row in rows:
            label = row["metric"]
            suffix = f" · human_verified={row['human_verified']}"
            if row["draft"]:
                suffix += " · draft labels"
            st.write(f"**{label}**: {_fmt_metric(row['value'])}{suffix}")
        shown_refusal = [r for r in rows if r["metric"] in refusal_keys]
        if not shown_refusal:
            st.caption(
                f"Refusal metrics: not present in this file · human_verified={latest.n_human_verified}"
            )
        shown_cite = [r for r in rows if r["metric"] in cite_keys]
        if not shown_cite:
            st.caption(
                f"Citation validity: not present in this file · human_verified={latest.n_human_verified}"
            )
    else:
        st.info(empty_state_message())

    if abl and abl.ablations:
        st.markdown("#### Ablation table")
        if abl.is_draft:
            st.warning("**draft labels** — ablation figures are unverified.")
        st.caption(f"human_verified={abl.n_human_verified} · file `{abl.path.name}`")
        table = []
        for name, vals in abl.ablations.items():
            table.append(
                {
                    "config": name,
                    "Recall@4": _fmt_metric(vals.get("Recall@4")),
                    "MRR": _fmt_metric(vals.get("MRR")),
                    "human_verified": abl.n_human_verified,
                }
            )
        st.dataframe(table, use_container_width=True, hide_index=True)

    st.markdown("#### Run history")
    hist = []
    for run in runs:
        if run.path.name.startswith("_") and not run.is_ablation:
            continue
        hist.append(
            {
                "date": str(run.run_date or "—"),
                "file": run.path.name,
                "commit": run.git_commit or "—",
                "split": run.split or ("ablation" if run.is_ablation else "—"),
                "human_verified": run.n_human_verified,
                "draft": "yes" if run.is_draft else "no",
            }
        )
    if hist:
        st.dataframe(hist, use_container_width=True, hide_index=True)
    else:
        st.caption("No dated evaluation runs in range.")


def render_analytics(client_factory: Callable) -> None:
    st.markdown('<p class="page-kicker">Operations</p>', unsafe_allow_html=True)
    st.markdown("## Analytics")
    st.caption("Live usage counters and offline evaluation results — no demo placeholders.")

    c_refresh, _ = st.columns([1, 3])
    with c_refresh:
        if st.button("Refresh", use_container_width=True):
            st.rerun()

    st.markdown("### Live usage")
    st.caption("Process metrics from the running API (cache hits, latency). Not evaluation scores.")
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
            st.markdown("#### Latency (live rolling window)")
            st.caption(latency.get("note") or "Samples since backend start — live usage only.")
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
            L2[1].metric("Live samples", (latency.get("total") or {}).get("count") or 0)

            if health:
                st.success(
                    f"API healthy · {health.get('app')} · "
                    f"LLM `{health.get('llm_provider')}` · "
                    f"embeddings `{health.get('embedding_provider', '—')}` · "
                    f"retrieval `{health.get('retrieval_strategy', 'hybrid_rrf')}`"
                )

    st.divider()
    # Ensure repo root on path for evals.results_browser
    import sys

    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    _render_eval_results()
