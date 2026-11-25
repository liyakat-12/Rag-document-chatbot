"""Conversational follow-up rewrite (Phase: chat.rewrite_followups, default off).

Offline path: when the new query is pronoun-heavy or very short, carry key entities
(fund names, scheme codes, document names) from the previous user turn — unless the
new query introduces a different topic's entities.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from backend.app.utils.logging import get_logger

logger = get_logger(__name__)

_PRONOUN_RE = re.compile(
    r"\b(it|its|they|them|their|this|that|these|those|the\s+(?:fund|scheme|document|sid|circular))\b",
    re.I,
)
_CODE_RE = re.compile(
    r"\b[A-Z]{2,}(?:/[A-Z0-9.\-]+){1,}\b|\b(?:INF|HDFC|MOTO|PPFAS|NIPPON)[A-Z0-9/\-]*\b",
    re.I,
)
_FUND_RE = re.compile(
    r"\b(?:HDFC|Kotak|Motilal(?:\s+Oswal)?|Nippon(?:\s+India)?|Parag\s+Parikh|PPFAS)"
    r"(?:\s+[\w\-]+)*?"
    r"(?:\s+(?:Mid\s*Cap|Midcap|Flexi\s*Cap|Growth|Emerging\s+Equity)\s+Fund"
    r"|\s+Fund)?\b",
    re.I,
)
_DOC_RE = re.compile(
    r"\b(?:SID|Scheme\s+Information\s+Document|SEBI\s+(?:Master\s+)?Circular"
    r"|master\s+circular|commodity\s+circular)[^\n,]{0,40}",
    re.I,
)
_SHORT_MAX_WORDS = 6


@dataclass
class FollowupRewrite:
    original: str
    rewritten: str
    method: str  # none | offline_entities | llm
    entities_carried: list[str]
    skipped_reason: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "original_query": self.original,
            "rewritten_query": self.rewritten,
            "rewrite_method": self.method,
            "entities_carried": list(self.entities_carried),
            "skipped_reason": self.skipped_reason or None,
        }


def extract_key_entities(text: str) -> list[str]:
    """Fund names, codes, and document titles from a turn."""
    text = text or ""
    found: list[str] = []
    for rx in (_FUND_RE, _CODE_RE, _DOC_RE):
        for m in rx.finditer(text):
            ent = re.sub(r"\s+", " ", m.group(0)).strip(" ,.;:")
            if len(ent) >= 3 and ent.lower() not in {e.lower() for e in found}:
                found.append(ent)
    return found


def _needs_rewrite(query: str) -> bool:
    q = (query or "").strip()
    if not q:
        return False
    words = q.split()
    if len(words) <= _SHORT_MAX_WORDS:
        return True
    if _PRONOUN_RE.search(q):
        return True
    return False


def _topic_changed(prior_entities: Sequence[str], new_entities: Sequence[str]) -> bool:
    """True when the new query names a different fund/doc family than the prior turn."""
    if not new_entities or not prior_entities:
        return False
    prior_l = {e.lower() for e in prior_entities}
    # If any new entity shares a token with prior, treat as same topic
    for ne in new_entities:
        nl = ne.lower()
        if nl in prior_l:
            return False
        # Shared significant token (e.g. "HDFC" in both)
        ntoks = {t for t in re.split(r"[\s/]+", nl) if len(t) > 2}
        for pe in prior_l:
            ptoks = {t for t in re.split(r"[\s/]+", pe) if len(t) > 2}
            if ntoks & ptoks:
                return False
    return True


def rewrite_followup_offline(
    query: str,
    recent_user_questions: Sequence[str],
) -> FollowupRewrite:
    """Carry prior-turn entities into short/pronoun follow-ups (no LLM)."""
    original = (query or "").strip()
    prior = ""
    for q in reversed(list(recent_user_questions or [])):
        if (q or "").strip():
            prior = q.strip()
            break
    if not prior:
        return FollowupRewrite(original, original, "none", [], "no_prior_turn")
    if not _needs_rewrite(original):
        return FollowupRewrite(original, original, "none", [], "standalone_query")

    prior_ents = extract_key_entities(prior)
    new_ents = extract_key_entities(original)
    if _topic_changed(prior_ents, new_ents):
        return FollowupRewrite(
            original, original, "none", [], "topic_changed"
        )
    if not prior_ents:
        # Fall back: prepend prior question for context
        rewritten = f"{prior.rstrip('?')} — {original}"
        return FollowupRewrite(original, rewritten, "offline_entities", [], "")

    carried = prior_ents[:5]
    entity_clause = ", ".join(carried)
    rewritten = f"{original.rstrip('?')} (regarding {entity_clause})"
    return FollowupRewrite(original, rewritten, "offline_entities", carried, "")


async def rewrite_followup_llm(
    query: str,
    recent_user_questions: Sequence[str],
    recent_assistant: Sequence[str] | None = None,
) -> FollowupRewrite:
    """Use the configured chat LLM to rewrite into a standalone retrieval query."""
    from backend.app.rag.llm_factory import get_chat_llm

    original = (query or "").strip()
    prior_turns = list(recent_user_questions or [])[-3:]
    if not prior_turns:
        return FollowupRewrite(original, original, "none", [], "no_prior_turn")
    history_lines = []
    for i, u in enumerate(prior_turns):
        history_lines.append(f"User: {u}")
        if recent_assistant and i < len(recent_assistant):
            history_lines.append(f"Assistant: {(recent_assistant[i] or '')[:300]}")
    prompt = (
        "Rewrite the latest user message into a standalone search query that includes "
        "all necessary entity names from the conversation. Output ONLY the rewritten "
        "query, nothing else.\n\n"
        f"Conversation:\n" + "\n".join(history_lines) + "\n"
        f"Latest user message: {original}\n"
        "Standalone query:"
    )
    try:
        llm = get_chat_llm()
        resp = await llm.ainvoke(prompt)
        text = getattr(resp, "content", None) or str(resp)
        rewritten = (text or "").strip().splitlines()[0].strip().strip('"')
        if not rewritten or len(rewritten) < 3:
            return rewrite_followup_offline(original, prior_turns)
        return FollowupRewrite(
            original,
            rewritten,
            "llm",
            extract_key_entities(prior_turns[-1]),
            "",
        )
    except Exception as exc:
        logger.warning("followup_llm_failed", error=str(exc))
        return rewrite_followup_offline(original, prior_turns)


async def rewrite_followup(
    query: str,
    recent_user_questions: Sequence[str],
    *,
    use_llm: bool = False,
    recent_assistant: Sequence[str] | None = None,
) -> FollowupRewrite:
    if use_llm:
        from backend.app.config import get_settings

        provider = (get_settings().llm_provider or "").lower()
        if provider and provider != "extractive":
            return await rewrite_followup_llm(
                query, recent_user_questions, recent_assistant=recent_assistant
            )
    return rewrite_followup_offline(query, recent_user_questions)
