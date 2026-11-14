"""Sentence-level extractive answering (answer.sentence_select, default off)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

from langchain_core.documents import Document as LCDocument

_WORD_RE = re.compile(r"[a-z0-9]{2,}", re.I)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", re.I)
_PHONE_RE = re.compile(
    r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)"
)
_URL_RE = re.compile(r"https?://|www\.", re.I)
_SOCIAL_LINE_RE = re.compile(
    r"\b(linkedin|github|twitter|instagram|facebook)\b.*\|.*"
    r"|\|.*\b(linkedin|github|twitter|instagram|facebook)\b",
    re.I,
)
_CONTACT_Q_RE = re.compile(
    r"\b(email|phone|contact|linkedin|github|url|website|mobile|call)\b",
    re.I,
)
_STOP = {
    "what", "which", "when", "where", "that", "this", "with", "from", "have",
    "does", "about", "your", "document", "documents", "please", "tell", "give",
    "list", "the", "and", "are", "was", "were", "for", "how", "who", "why",
    "any", "main", "points",
}


@dataclass
class SelectedSentence:
    text: str
    filename: str
    page_number: int
    chunk_id: str
    document_id: str
    score: float
    doc_order: int  # original order in retrieved stream


@dataclass
class SentenceAnswer:
    answer: str
    sentences: list[SelectedSentence] = field(default_factory=list)
    word_count: int = 0

    def citation_dicts(self) -> list[dict[str, Any]]:
        """One source entry per selected sentence (file + page), content = sentence."""
        out: list[dict[str, Any]] = []
        for s in self.sentences:
            out.append(
                {
                    "document_id": s.document_id,
                    "filename": s.filename,
                    "page_number": s.page_number,
                    "chunk_id": s.chunk_id,
                    "content": s.text,
                    "score": round(s.score, 4),
                    "location_type": "page",
                    "location": str(s.page_number),
                    "file_type": "pdf",
                    "selected_sentence": True,
                }
            )
        return out


def split_into_sentences(text: str) -> list[str]:
    """Split on ., !, ?, bullets, and '|' separators."""
    if not text:
        return []
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    # Treat bullets / pipes as hard breaks before punctuation split
    t = re.sub(r"[•●▪◦]\s*", "\n", t)
    t = re.sub(r"\s*\|\s*", "\n", t)
    parts: list[str] = []
    for para in re.split(r"[\n]+", t):
        para = para.strip()
        if not para:
            continue
        # Strip leading bullet remnants
        para = re.sub(r"^[-–—*]\s+", "", para)
        segs = re.split(r"(?<=[.!?])\s+", para)
        for s in segs:
            s = s.strip()
            if len(s) >= 12:
                parts.append(s)
    return parts


def is_contact_line(text: str) -> bool:
    if _EMAIL_RE.search(text):
        return True
    if _URL_RE.search(text):
        return True
    if _PHONE_RE.search(text):
        return True
    if _SOCIAL_LINE_RE.search(text):
        return True
    return False


def _term_overlap(query: str, sentence: str) -> float:
    qw = {w.lower() for w in _WORD_RE.findall(query) if w.lower() not in _STOP}
    if not qw:
        return 0.0
    sw = {w.lower() for w in _WORD_RE.findall(sentence)}
    return len(qw & sw) / len(qw)


def _cosine(a: Sequence[float], b: Sequence[float]) -> float:
    import math

    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a))
    nb = math.sqrt(sum(y * y for y in b))
    if na <= 0 or nb <= 0:
        return 0.0
    return dot / (na * nb)


def _cap_words(sentences: list[str], max_words: int = 60) -> list[str]:
    kept: list[str] = []
    total = 0
    for s in sentences:
        w = len(s.split())
        if kept and total + w > max_words:
            break
        kept.append(s)
        total += w
        if total >= max_words:
            break
    return kept


def select_answer_sentences(
    query: str,
    docs_with_scores: list[tuple[LCDocument, float]],
    *,
    top_n: int = 3,
    max_words: int = 60,
    use_embeddings: bool = True,
) -> SentenceAnswer:
    """Pick top 2–3 sentences by embedding + term overlap; return in document order."""
    from backend.app.rag.qa_chain import NOT_FOUND_MESSAGE

    allow_contact = bool(_CONTACT_Q_RE.search(query or ""))
    candidates: list[SelectedSentence] = []
    order = 0
    for doc, _score in docs_with_scores:
        meta = doc.metadata or {}
        for sent in split_into_sentences(doc.page_content or ""):
            if not allow_contact and is_contact_line(sent):
                continue
            candidates.append(
                SelectedSentence(
                    text=sent,
                    filename=str(meta.get("filename") or "document.pdf"),
                    page_number=int(meta.get("page_number") or 1),
                    chunk_id=str(meta.get("chunk_id") or ""),
                    document_id=str(meta.get("document_id") or ""),
                    score=0.0,
                    doc_order=order,
                )
            )
            order += 1

    if not candidates:
        return SentenceAnswer(answer=NOT_FOUND_MESSAGE, sentences=[], word_count=0)

    query_emb: Optional[list[float]] = None
    sent_embs: dict[int, list[float]] = {}
    if use_embeddings:
        try:
            from backend.app.rag.llm_factory import get_shared_embeddings

            emb = get_shared_embeddings()
            query_emb = list(emb.embed_query(query))
            # Batch embed unique sentences (cap for latency)
            texts = [c.text for c in candidates[:40]]
            vectors = emb.embed_documents(texts)
            for i, vec in enumerate(vectors):
                sent_embs[i] = list(vec)
        except Exception:
            query_emb = None

    scored: list[SelectedSentence] = []
    for i, c in enumerate(candidates[:40] if use_embeddings else candidates):
        term = _term_overlap(query, c.text)
        sim = 0.0
        if query_emb is not None and i in sent_embs:
            sim = _cosine(query_emb, sent_embs[i])
        # Blend: embeddings when available, else term-only
        c.score = (0.55 * sim + 0.45 * term) if query_emb is not None else term
        scored.append(c)

    scored.sort(key=lambda s: s.score, reverse=True)
    # Keep only positive signal
    top = [s for s in scored if s.score > 0][: max(2, min(top_n, 3))]
    if not top:
        top = scored[:2]

    # Document order
    top.sort(key=lambda s: s.doc_order)
    texts = _cap_words([s.text for s in top], max_words=max_words)
    # Align sentence objects to capped texts
    selected = []
    for s in top:
        if s.text in texts:
            selected.append(s)
        if len(selected) >= len(texts):
            break

    body = " ".join(texts).strip()
    if not body:
        return SentenceAnswer(answer=NOT_FOUND_MESSAGE, sentences=[], word_count=0)
    answer = (
        "**Answer from your documents** (sentence-select · offline)\n\n" + body
    )
    return SentenceAnswer(
        answer=answer,
        sentences=selected,
        word_count=len(body.split()),
    )


def highlight_sentences_in_chunk(chunk: str, sentences: Sequence[str]) -> str:
    """Mark selected sentences in chunk text with >>>…<<< for UI context."""
    out = chunk or ""
    for s in sentences:
        if s and s in out:
            out = out.replace(s, f">>>{s}<<<", 1)
    return out
