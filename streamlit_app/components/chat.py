"""Chat page — empty states, conversation, streaming answers."""

from __future__ import annotations

import time
from typing import Any, Callable

import streamlit as st

import components._pathfix  # noqa: F401
from components import friendly_error
from components.citation_viewer import render_citation_viewer_panel
from components.sources import render_confidence, render_retrieval_details, render_sources

# Fallback only — prefer heading-derived starters from components.headings
_FALLBACK_SUGGESTIONS = [
    "What is this document about?",
    "List the main section headings in this document.",
    "What names, dates, or numbers appear near the start?",
    "Which sections cover skills or experience?",
]

NOT_FOUND_SNIPPET = "couldn't find that information"

_STATUS_CSS = {
    "answered": "status-ok",
    "weak_evidence": "status-warn",
    "not_found": "status-err",
}


def _refusal_badge(msg: dict[str, Any]) -> tuple[str, str] | None:
    """Return (label, css) when refusal meta is present; else None."""
    retrieval = msg.get("retrieval") or {}
    refusal = retrieval.get("refusal") or {}
    decision = refusal.get("decision")
    if not decision:
        return None
    labels = {
        "answered": "Answered",
        "weak_evidence": "Weak evidence",
        "not_found": "Not found",
    }
    return labels.get(str(decision), str(decision)), _STATUS_CSS.get(str(decision), "status-warn")


def _find_prior_user_prompt(messages: list[dict[str, Any]], assistant_index: int) -> str | None:
    for j in range(assistant_index - 1, -1, -1):
        if messages[j].get("role") == "user":
            return messages[j].get("content") or None
    return None


def _is_greeting_turn(msg: dict[str, Any]) -> bool:
    retrieval = msg.get("retrieval") or {}
    if retrieval.get("strategy") == "greeting":
        return True
    # Historical sessions may lack retrieval metadata
    sources = msg.get("sources") or []
    conf = msg.get("confidence")
    content = (msg.get("content") or "").lower()
    if not sources and (conf is None or conf == 0) and (
        "hello" in content or "hi," in content or "documind" in content[:80]
    ):
        return True
    return False


def _is_weak_evidence(msg: dict[str, Any]) -> bool:
    content = (msg.get("content") or "").lower()
    if NOT_FOUND_SNIPPET in content:
        return True
    conf = msg.get("confidence")
    sources = msg.get("sources") or []
    return conf is not None and float(conf) <= 0 and not sources


def render_empty_library(*, max_mb: int = 40) -> None:
    """First-run state when nothing is indexed — no fake suggestions or stats."""
    st.markdown(
        """
        <div class="hero-wrap">
          <p class="brand-hero">DocuMind AI</p>
          <p class="hero-title">Upload documents to begin</p>
          <p class="hero-sub">
            Index private PDFs, then ask questions grounded in retrieved passages
            with file and page citations. Nothing is answered until you add documents.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"Supported: PDF · up to {max_mb} MB each · text-extractable files only")
    if st.button("Upload documents", type="primary", use_container_width=True):
        st.session_state.page = "Documents"
        st.session_state["_force_page"] = "Documents"
        st.rerun()


def render_welcome_with_docs(
    on_suggest: Callable[[str], None],
    *,
    docs: list[dict[str, Any]] | None = None,
) -> None:
    from components.headings import starters_for_docs

    st.markdown(
        """
        <div class="hero-wrap">
          <p class="brand-hero">DocuMind AI</p>
          <p class="hero-title">Ask your documents</p>
          <p class="hero-sub">
            Answers stay grounded in retrieved passages with file and page citations.
            If evidence is weak, DocuMind says so instead of inventing facts.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p class="nav-hint" style="text-align:center;margin-top:0.25rem;">Try a question</p>',
        unsafe_allow_html=True,
    )
    scoped_ids = set(st.session_state.get("selected_document_ids") or [])
    pool = docs or []
    if scoped_ids:
        pool = [d for d in pool if d.get("id") in scoped_ids] or pool
    suggestions = starters_for_docs(pool) or list(_FALLBACK_SUGGESTIONS)
    cols = st.columns(2)
    for i, q in enumerate(suggestions):
        with cols[i % 2]:
            if st.button(q, key=f"suggest_{i}", use_container_width=True):
                on_suggest(q)


def _display_answer(content: str) -> str:
    """Strip developer mode tags from answer headers (UI only)."""
    import re

    text = content or ""
    text = re.sub(
        r"(\*\*Answer from your documents\*\*|^\*\*Document summary\*\*)"
        r"\s*\([^)]*offline[^)]*\)\s*",
        r"\1\n\n",
        text,
        flags=re.I | re.M,
    )
    text = re.sub(
        r"\(extractive\s*·\s*offline[^)]*\)",
        "",
        text,
        flags=re.I,
    )
    return text.strip()


def _render_scope_chip(docs: list[dict[str, Any]]) -> None:
    """Single scope control above the composer (chip label = only scope UI)."""
    if not docs:
        return
    from components import truncate_at_word

    seen: dict[str, int] = {}
    label_to_id = {_doc_label(d, seen): d["id"] for d in docs}
    current_ids = set(st.session_state.get("selected_document_ids") or [])
    default_labels = [lab for lab, did in label_to_id.items() if did in current_ids]
    if default_labels:
        if len(default_labels) == 1:
            chip = f"Searching: {truncate_at_word(default_labels[0], 36)} ▾"
        else:
            chip = f"Searching: {len(default_labels)} documents ▾"
    else:
        chip = f"All documents ({len(docs)}) ▾"
    # One control only — no separate "Scoped to N of M" caption
    with st.popover(chip, use_container_width=True):
        chosen = st.multiselect(
            "Documents",
            options=list(label_to_id.keys()),
            default=default_labels,
            help="Leave empty to search all indexed documents.",
            key="search_in_labels",
            label_visibility="collapsed",
        )
        st.session_state.selected_document_ids = [label_to_id[lab] for lab in chosen]


def _selected_document_ids() -> list[str] | None:
    """Return active document filter, or None to search all indexed docs."""
    ids = st.session_state.get("selected_document_ids") or []
    return list(ids) if ids else None


def _doc_label(doc: dict[str, Any], seen: dict[str, int]) -> str:
    """Human filename; disambiguate duplicates without exposing full UUIDs."""
    name = (doc.get("original_filename") or "document.pdf").strip()
    count = seen.get(name, 0)
    seen[name] = count + 1
    if count == 0:
        return name
    return f"{name} ({count + 1})"


def _run_chat_turn(client_factory: Callable, prompt: str) -> None:
    st.session_state.messages.append({"role": "user", "content": prompt})
    st.session_state["chat_loading"] = True
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full = ""
        done_event: dict[str, Any] = {}
        retrieval: dict[str, Any] = {}
        # Extractive answers are near-instant — one non-stream call beats SSE + many UI updates
        use_fast = (st.session_state.get("llm_provider") or "") == "extractive"
        try:
            if use_fast:
                with st.spinner("Searching documents…"):
                    result = client_factory().chat(
                        prompt,
                        session_id=st.session_state.session_id,
                        document_ids=_selected_document_ids(),
                    )
                if result.get("session_id"):
                    st.session_state.session_id = result["session_id"]
                full = result.get("answer") or ""
                placeholder.markdown(full)
                done_event = result
                retrieval = result.get("retrieval") or {}
            else:
                status = st.empty()
                status.caption("Retrieving evidence…")
                for event in client_factory().chat_stream(
                    prompt,
                    session_id=st.session_state.session_id,
                    document_ids=_selected_document_ids(),
                ):
                    if event.get("event") == "meta":
                        if event.get("session_id"):
                            st.session_state.session_id = event["session_id"]
                        retrieval = event.get("retrieval") or retrieval
                        status.caption(
                            "Serving cached answer…"
                            if event.get("cached")
                            else "Generating answer…"
                        )
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
                status.empty()
            st.session_state.pop("last_failed_prompt", None)
        except Exception as exc:
            err = friendly_error(exc)
            # Never surface stack traces in the chat transcript
            if "Traceback" in str(exc) or "Traceback" in err:
                err = "Something went wrong while answering. Please try again."
            placeholder.error(err)
            full = err
            st.session_state["last_failed_prompt"] = prompt
            st.session_state["chat_loading"] = False
            assistant_msg = {
                "id": None,
                "role": "assistant",
                "content": full,
                "confidence": 0.0,
                "sources": [],
                "cached": False,
                "retrieval": {},
                "timings": {},
                "rating": "none",
                "is_error": True,
            }
            st.session_state.messages.append(assistant_msg)
            st.rerun()
            return

        st.session_state["chat_loading"] = False
        st.session_state.pop("last_failed_prompt", None)
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
            "is_error": False,
        }
        st.session_state.messages.append(assistant_msg)
        st.rerun()


def render_chat(client_factory: Callable, *, llm_provider: str = "") -> None:
    import os

    max_mb = int(os.getenv("MAX_UPLOAD_SIZE_MB", "40"))
    pending = st.session_state.pop("pending_prompt", None)
    # Keep provider in session for Settings / status tip (no user-facing banner)
    if llm_provider:
        st.session_state.llm_provider = llm_provider

    backend_ok = bool(st.session_state.get("backend_ok"))
    if not backend_ok:
        st.warning(
            "Backend unavailable. Chat, upload, and search require the API. "
            "Open **Settings** to retry after starting the backend."
        )

    # Document scope — cache list briefly to avoid an HTTP round-trip every Streamlit rerun
    docs = st.session_state.get("_indexed_docs_cache")
    cache_at = float(st.session_state.get("_indexed_docs_cache_at") or 0)

    if backend_ok and (docs is None or (time.time() - cache_at) > 15):
        try:
            docs = [
                d
                for d in client_factory().list_documents()
                if (d.get("status") or "").lower() == "indexed"
            ]
            st.session_state._indexed_docs_cache = docs
            st.session_state._indexed_docs_cache_at = time.time()
        except Exception:
            docs = []
            st.session_state.pop("_indexed_docs_cache", None)
            st.session_state.pop("_indexed_docs_cache_at", None)
    elif not backend_ok:
        docs = []

    docs = docs or []

    # Prune selected IDs that no longer exist (deleted / failed indexing)
    valid_ids = {d["id"] for d in docs}
    selected = [x for x in (st.session_state.get("selected_document_ids") or []) if x in valid_ids]
    if selected != (st.session_state.get("selected_document_ids") or []):
        st.session_state.selected_document_ids = selected
        if not selected and st.session_state.get("_had_stale_scope"):
            st.info("A previously selected document is no longer indexed. Scope reset to all documents.")
        st.session_state._had_stale_scope = False
    elif not selected and st.session_state.get("selected_document_ids"):
        st.session_state._had_stale_scope = True

    if not docs:
        if not st.session_state.messages and pending is None:
            render_empty_library(max_mb=max_mb)
        else:
            st.info("No indexed documents. Open **Documents** to upload a PDF before asking grounded questions.")
        if pending:
            st.warning("Upload and index a document before asking questions.")
            return
        # Still allow greetings / empty composer when library is empty? Block grounded Qs.
        prompt = st.chat_input(
            "Upload documents first…" if not st.session_state.messages else "Ask about your documents…"
        )
        if prompt and docs:
            _run_chat_turn(client_factory, prompt)
        elif prompt and not docs:
            # Allow short greetings via API; otherwise guide the user to upload
            import re

            greeting = bool(
                re.fullmatch(
                    r"(hi|hello|hey|hi there|good (morning|afternoon|evening))[!?.]*",
                    prompt.strip(),
                    flags=re.IGNORECASE,
                )
            )
            if greeting and backend_ok:
                _run_chat_turn(client_factory, prompt)
            else:
                st.session_state.messages.append({"role": "user", "content": prompt})
                st.session_state.messages.append(
                    {
                        "role": "assistant",
                        "content": (
                            "There are no indexed documents yet. "
                            "Open **Documents**, upload a PDF, wait for indexing to finish, then ask again."
                        ),
                        "confidence": 0.0,
                        "sources": [],
                        "retrieval": {"strategy": "empty_library"},
                        "timings": {},
                        "rating": "none",
                    }
                )
                st.rerun()
        return

    if not st.session_state.messages and pending is None:
        def _suggest(q: str) -> None:
            st.session_state.pending_prompt = q
            st.rerun()

        render_welcome_with_docs(_suggest, docs=docs)
    else:
        if st.session_state.get("chat_loading"):
            st.caption("Working…")

        for i, msg in enumerate(st.session_state.messages):
            with st.chat_message(msg["role"]):
                if msg["role"] != "assistant":
                    st.markdown(msg["content"])
                    continue

                is_error = bool(msg.get("is_error")) or bool(
                    st.session_state.get("last_failed_prompt")
                    and i == len(st.session_state.messages) - 1
                    and not msg.get("id")
                )
                is_greeting = _is_greeting_turn(msg)
                is_weak = _is_weak_evidence(msg)
                badge = _refusal_badge(msg)

                # Card: status → answer → sources → hover actions
                if badge:
                    label, css = badge
                    reason = ((msg.get("retrieval") or {}).get("refusal") or {}).get("reason") or ""
                    st.markdown(
                        f'<span class="{css}">{label}</span>',
                        unsafe_allow_html=True,
                    )
                    if reason:
                        st.caption(reason)
                elif not is_greeting and not is_error and not is_weak:
                    render_confidence(
                        msg.get("confidence"),
                        sources=msg.get("sources"),
                    )
                if msg.get("cached"):
                    st.markdown('<span class="meta-chip">Cached</span>', unsafe_allow_html=True)

                st.markdown(_display_answer(msg.get("content") or ""))

                if is_greeting or is_error:
                    prior = _find_prior_user_prompt(st.session_state.messages, i)
                    st.markdown('<div class="msg-actions">', unsafe_allow_html=True)
                    a1, a2 = st.columns([1, 1])
                    with a1:
                        st.download_button(
                            "⎘ Copy",
                            data=msg.get("content") or "",
                            file_name="documind-answer.txt",
                            mime="text/plain",
                            key=f"copy_{i}",
                        )
                    with a2:
                        if is_error and st.button("↻ Retry", key=f"retry_{i}"):
                            failed = st.session_state.pop("last_failed_prompt", None)
                            prompt_retry = failed or prior
                            if len(st.session_state.messages) >= 2:
                                st.session_state.messages = st.session_state.messages[:-2]
                            if prompt_retry:
                                st.session_state.pending_prompt = prompt_retry
                            st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)
                    continue

                if is_weak:
                    st.info(
                        "Insufficient evidence in the indexed documents for this question. "
                        "Try rephrasing, changing scope, or uploading a covering PDF."
                    )
                    if msg.get("sources"):
                        render_sources(msg.get("sources"), msg_index=i)
                else:
                    render_sources(msg.get("sources"), msg_index=i)
                    render_retrieval_details(
                        msg.get("retrieval"),
                        msg.get("timings"),
                        sources=msg.get("sources"),
                    )
                    if msg.get("id"):
                        b1, b2, b3 = st.columns([1.2, 1.4, 2])
                        with b1:
                            if st.button("Helpful", key=f"up_{i}"):
                                try:
                                    client_factory().rate_message(msg["id"], "up")
                                    st.session_state.messages[i]["rating"] = "up"
                                    st.toast("Thanks for the feedback")
                                except Exception as exc:
                                    st.error(friendly_error(exc))
                        with b2:
                            if st.button("Not helpful", key=f"down_{i}"):
                                try:
                                    client_factory().rate_message(msg["id"], "down")
                                    st.session_state.messages[i]["rating"] = "down"
                                    st.toast("Thanks for the feedback")
                                except Exception as exc:
                                    st.error(friendly_error(exc))
                        with b3:
                            if msg.get("rating") not in (None, "none"):
                                st.caption(f"Rated: {msg['rating']}")

                prior = _find_prior_user_prompt(st.session_state.messages, i)
                st.markdown('<div class="msg-actions">', unsafe_allow_html=True)
                c1, c2 = st.columns([1, 1])
                with c1:
                    st.download_button(
                        "⎘ Copy",
                        data=msg.get("content") or "",
                        file_name="documind-answer.txt",
                        mime="text/plain",
                        key=f"copy_{i}",
                    )
                with c2:
                    if prior and st.button("↻ Regenerate", key=f"regen_{i}"):
                        st.session_state.messages = st.session_state.messages[
                            : i - 1 if i > 0 else 0
                        ]
                        st.session_state.pending_prompt = prior
                        st.session_state.pop("last_failed_prompt", None)
                        st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

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

    render_citation_viewer_panel(client_factory)

    if pending:
        _run_chat_turn(client_factory, pending)
        return

    _render_scope_chip(docs)
    prompt = st.chat_input("Ask a question about your documents…")
    if prompt:
        _run_chat_turn(client_factory, prompt)
