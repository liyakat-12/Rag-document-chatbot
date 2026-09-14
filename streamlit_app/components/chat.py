"""Chat page — empty state, conversation, streaming answers."""

from __future__ import annotations

from typing import Any, Callable

import streamlit as st

import components._pathfix  # noqa: F401
from components import friendly_error
from components.sources import render_confidence, render_retrieval_details, render_sources

SUGGESTIONS = [
    "What is this document about?",
    "Summarize the key points.",
    "What are the main topics discussed?",
    "What important information should I know?",
]


def render_empty_state(on_suggest: Callable[[str], None], *, mode_note: str = "") -> None:
    st.markdown('<p class="brand-hero">DocuMind AI</p>', unsafe_allow_html=True)
    st.markdown('<p class="hero-title">Ask your documents anything</p>', unsafe_allow_html=True)
    st.markdown(
        '<p class="hero-sub">Upload PDFs and get answers grounded in your source material.</p>',
        unsafe_allow_html=True,
    )
    if mode_note:
        st.caption(mode_note)

    cols = st.columns(2)
    for i, q in enumerate(SUGGESTIONS):
        with cols[i % 2]:
            st.markdown(f'<div class="suggest-card">{q}</div>', unsafe_allow_html=True)
            if st.button("Ask", key=f"suggest_{i}", use_container_width=True):
                on_suggest(q)


def _run_chat_turn(client_factory: Callable, prompt: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full = ""
        done_event: dict[str, Any] = {}
        retrieval: dict[str, Any] = {}
        try:
            for event in client_factory().chat_stream(
                prompt, session_id=st.session_state.session_id
            ):
                if event.get("event") == "meta":
                    if event.get("session_id"):
                        st.session_state.session_id = event["session_id"]
                    retrieval = event.get("retrieval") or retrieval
                elif event.get("event") == "token":
                    full += event.get("content") or ""
                    placeholder.markdown(full + " ▌")
                elif event.get("event") == "done":
                    done_event = event
                    full = event.get("answer") or full
                    retrieval = event.get("retrieval") or retrieval
                    placeholder.markdown(full)
                elif event.get("event") == "error":
                    raise RuntimeError(event.get("content") or "Chat failed")
        except Exception as exc:
            err = friendly_error(exc)
            placeholder.error(err)
            full = err

        assistant_msg = {
            "id": done_event.get("message_id"),
            "role": "assistant",
            "content": full,
            "confidence": done_event.get("confidence"),
            "sources": done_event.get("sources") or [],
            "cached": done_event.get("cached", False),
            "retrieval": retrieval or done_event.get("retrieval") or {},
            "timings": done_event.get("timings") or {},
            "rating": "none",
        }
        st.session_state.messages.append(assistant_msg)
        st.rerun()


def render_chat(client_factory: Callable, *, llm_provider: str = "") -> None:
    pending = st.session_state.pop("pending_prompt", None)
    mode_note = ""
    if llm_provider == "extractive":
        mode_note = "Offline mode · Extractive answers"

    if not st.session_state.messages and pending is None:
        def _suggest(q: str) -> None:
            st.session_state.pending_prompt = q
            st.rerun()

        render_empty_state(_suggest, mode_note=mode_note)
    else:
        if mode_note:
            st.caption(mode_note)

        for i, msg in enumerate(st.session_state.messages):
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])
                if msg["role"] == "assistant":
                    st.markdown("##### Sources")
                    if msg.get("cached"):
                        st.markdown('<span class="meta-chip">Cached</span>', unsafe_allow_html=True)
                    render_confidence(msg.get("confidence"))
                    render_sources(msg.get("sources"))
                    render_retrieval_details(msg.get("retrieval"), msg.get("timings"))

                    st.caption("Was this answer helpful?")
                    b1, b2, b3, _ = st.columns([1, 1, 1, 3])
                    with b1:
                        if st.button("Helpful", key=f"up_{i}") and msg.get("id"):
                            try:
                                client_factory().rate_message(msg["id"], "up")
                                st.session_state.messages[i]["rating"] = "up"
                                st.toast("Thanks for the feedback")
                            except Exception as exc:
                                st.error(friendly_error(exc))
                    with b2:
                        if st.button("Not helpful", key=f"down_{i}") and msg.get("id"):
                            try:
                                client_factory().rate_message(msg["id"], "down")
                                st.session_state.messages[i]["rating"] = "down"
                                st.toast("Thanks for the feedback")
                            except Exception as exc:
                                st.error(friendly_error(exc))
                    with b3:
                        if msg.get("rating") not in (None, "none"):
                            st.caption(f"Rated: {msg['rating']}")

        if st.session_state.session_id:
            try:
                pdf_bytes = client_factory().export_pdf(st.session_state.session_id)
                st.download_button(
                    "Download conversation as PDF",
                    data=pdf_bytes,
                    file_name=f"documind-{st.session_state.session_id[:8]}.pdf",
                    mime="application/pdf",
                )
            except Exception as exc:
                st.caption(f"Export unavailable: {friendly_error(exc)}")

    if pending:
        _run_chat_turn(client_factory, pending)
        return

    prompt = st.chat_input("Ask a question about your documents…")
    if prompt:
        _run_chat_turn(client_factory, prompt)
