"""Sentence-level extractive answering (answer.sentence_select, default off).

Variants (ablation):
  term | crossencoder | crossencoder_context | clean_chunk
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, Optional, Sequence

from langchain_core.documents import Document as LCDocument

ScoreMode = Literal["term", "crossencoder", "crossencoder_context", "clean_chunk"]

_WORD_RE = re.compile(r"[a-z0-9]{2,}", re.I)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b", re.I)
_PHONE_RE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
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

# Protect these from sentence splits on the trailing period
_ABBREV = {
    "b.tech", "m.tech", "b.e", "m.e", "b.sc", "m.sc", "ph.d", "dr", "mr", "mrs",
    "ms", "rs", "no", "nos", "vol", "fig", "eq", "approx", "e.g", "i.e", "vs",
    "etc", "inc", "ltd", "dept", "univ",
}


@dataclass
class SelectedSentence:
    text: str
    filename: str
    page_number: int
    chunk_id: str
    document_id: str
    score: float
    doc_order: int
    chunk_text: str = ""


@dataclass
class SentenceAnswer:
    answer: str
    sentences: list[SelectedSentence] = field(default_factory=list)
    word_count: int = 0
    variant: str = "term"
    context_chunk: str = ""

    def citation_dicts(self) -> list[dict[str, Any]]:
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


def _protect_abbreviations(text: str) -> str:
    """Replace abbrev periods with a sentinel so split won't cut them."""
    out = text
    # Codes / dotted identifiers like HDFC/O/E/MIF/07/04/0015 stay intact (no spaces)
    # Decimal / percent: 7.92, 0.20%
    out = re.sub(r"(\d)\.(\d)", r"\1⟦DOT⟧\2", out)
    # R² = 0.69 style already covered by decimal; also R2 = 0.69
    out = re.sub(r"\b([Rr]²?)\s*=\s*", r"\1 = ", out)
    # Known abbreviations (case-insensitive word before period)
    for ab in sorted(_ABBREV, key=len, reverse=True):
        out = re.sub(
            rf"\b({re.escape(ab)})\.",
            lambda m: m.group(1).replace(".", "⟦DOT⟧") + "⟦DOT⟧",
            out,
            flags=re.I,
        )
    # Single-letter initials: "B. Tech" already handled; "U.S." style
    out = re.sub(r"\b([A-Za-z])\.([A-Za-z])\.", r"\1⟦DOT⟧\2⟦DOT⟧", out)
    return out


def _unprotect(text: str) -> str:
    return text.replace("⟦DOT⟧", ".")


def split_into_sentences(text: str) -> list[str]:
    """Split on ., !, ?, bullets, and '|' — never inside decimals/abbrevs/codes."""
    if not text:
        return []
    t = text.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[•●▪◦]\s*", "\n", t)
    # Pipe breaks only when not inside a code-like token (no spaces around /)
    t = re.sub(r"(?<!\S)\|(?!\S)|\s\|\s", "\n", t)
    parts: list[str] = []
    for para in re.split(r"[\n]+", t):
        para = para.strip()
        if not para:
            continue
        para = re.sub(r"^[-–—*]\s+", "", para)
        protected = _protect_abbreviations(para)
        segs = re.split(r"(?<=[.!?])\s+", protected)
        for s in segs:
            s = _unprotect(s.strip())
            if len(s) >= 8:
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


def strip_contact_lines(text: str) -> str:
    kept = []
    for line in (text or "").splitlines():
        if is_contact_line(line):
            continue
        # Also drop inline contact-only sentences
        if is_contact_line(line.strip()):
            continue
        kept.append(line)
    # Filter sentence-level contact too
    body = "\n".join(kept)
    sents = [s for s in split_into_sentences(body) if not is_contact_line(s)]
    if sents:
        return " ".join(sents)
    return body


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


def _score_crossencoder(query: str, sentences: list[str]) -> list[float]:
    """Lazy-load CrossEncoder; fall back to term overlap on failure."""
    if not sentences:
        return []
    try:
        from backend.app.rag.reranker import get_cross_encoder

        model = get_cross_encoder()
        if model is None:
            return [_term_overlap(query, s) for s in sentences]
        pairs = [(query, s) for s in sentences]
        scores = model.predict(pairs)
        return [float(x) for x in scores]
    except Exception:
        return [_term_overlap(query, s) for s in sentences]


def _collect_candidates(
    query: str,
    docs_with_scores: list[tuple[LCDocument, float]],
) -> list[SelectedSentence]:
    allow_contact = bool(_CONTACT_Q_RE.search(query or ""))
    candidates: list[SelectedSentence] = []
    order = 0
    for doc, _score in docs_with_scores:
        meta = doc.metadata or {}
        chunk = doc.page_content or ""
        for sent in split_into_sentences(chunk):
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
                    chunk_text=chunk,
                )
            )
            order += 1
    return candidates


def select_answer_sentences(
    query: str,
    docs_with_scores: list[tuple[LCDocument, float]],
    *,
    top_n: int = 3,
    max_words: int = 60,
    use_embeddings: bool = True,
    mode: ScoreMode = "term",
) -> SentenceAnswer:
    """Select answer sentences (or clean_chunk) for the given mode."""
    from backend.app.rag.qa_chain import NOT_FOUND_MESSAGE
    from backend.app.utils.text import fix_hyphenation

    if mode == "clean_chunk":
        return _clean_chunk_answer(query, docs_with_scores, max_words=max_words)

    candidates = _collect_candidates(query, docs_with_scores)
    if not candidates:
        return SentenceAnswer(
            answer=NOT_FOUND_MESSAGE, sentences=[], word_count=0, variant=mode
        )

    texts = [c.text for c in candidates]
    if mode in {"crossencoder", "crossencoder_context"}:
        scores = _score_crossencoder(query, texts)
        for c, sc in zip(candidates, scores):
            c.score = float(sc)
    else:
        # term (+ optional embed blend)
        query_emb = None
        sent_embs: dict[int, list[float]] = {}
        if use_embeddings:
            try:
                from backend.app.rag.llm_factory import get_shared_embeddings

                emb = get_shared_embeddings()
                query_emb = list(emb.embed_query(query))
                vectors = emb.embed_documents(texts[:40])
                for i, vec in enumerate(vectors):
                    sent_embs[i] = list(vec)
            except Exception:
                query_emb = None
        for i, c in enumerate(candidates):
            term = _term_overlap(query, c.text)
            if query_emb is not None and i in sent_embs:
                c.score = 0.55 * _cosine(query_emb, sent_embs[i]) + 0.45 * term
            else:
                c.score = term

    # Deterministic sort: score desc, then doc_order, then chunk_id
    scored = sorted(
        candidates,
        key=lambda s: (-s.score, s.doc_order, s.chunk_id),
    )
    top = [s for s in scored if s.score > 0][: max(2, min(top_n, 3))]
    if not top:
        top = scored[:2]

    if mode == "crossencoder_context":
        # Expand each pick with neighbouring sentence from its chunk
        expanded: list[SelectedSentence] = []
        seen_text: set[str] = set()
        for s in top:
            sents = split_into_sentences(s.chunk_text)
            try:
                idx = next(i for i, t in enumerate(sents) if t == s.text)
            except StopIteration:
                idx = -1
            neigh: list[str] = []
            if idx > 0:
                neigh.append(sents[idx - 1])
            neigh.append(s.text)
            if 0 <= idx < len(sents) - 1:
                neigh.append(sents[idx + 1])
            merged = " ".join(neigh)
            if merged not in seen_text:
                seen_text.add(merged)
                expanded.append(
                    SelectedSentence(
                        text=merged,
                        filename=s.filename,
                        page_number=s.page_number,
                        chunk_id=s.chunk_id,
                        document_id=s.document_id,
                        score=s.score,
                        doc_order=s.doc_order,
                        chunk_text=s.chunk_text,
                    )
                )
        top = expanded

    top.sort(key=lambda s: s.doc_order)
    capped = _cap_words([s.text for s in top], max_words=max_words)
    selected = [s for s in top if s.text in capped][: len(capped)]
    # If context merge changed text, match by order
    if len(selected) < len(capped):
        selected = top[: len(capped)]
        for i, s in enumerate(selected):
            if i < len(capped):
                s.text = capped[i]

    body = " ".join(capped).strip()
    if not body:
        return SentenceAnswer(
            answer=NOT_FOUND_MESSAGE, sentences=[], word_count=0, variant=mode
        )
    answer = f"**Answer from your documents** ({mode} · offline)\n\n{body}"
    ctx = selected[0].chunk_text if selected else ""
    return SentenceAnswer(
        answer=answer,
        sentences=selected,
        word_count=len(body.split()),
        variant=mode,
        context_chunk=fix_hyphenation(ctx) if ctx else "",
    )


def _clean_chunk_answer(
    query: str,
    docs_with_scores: list[tuple[LCDocument, float]],
    *,
    max_words: int = 100,
) -> SentenceAnswer:
    from backend.app.rag.qa_chain import NOT_FOUND_MESSAGE
    from backend.app.utils.text import fix_hyphenation

    if not docs_with_scores:
        return SentenceAnswer(
            answer=NOT_FOUND_MESSAGE, sentences=[], word_count=0, variant="clean_chunk"
        )
    doc, score = docs_with_scores[0]
    meta = doc.metadata or {}
    cleaned = fix_hyphenation(strip_contact_lines(doc.page_content or ""))
    sents = split_into_sentences(cleaned)
    if not sents:
        return SentenceAnswer(
            answer=NOT_FOUND_MESSAGE, sentences=[], word_count=0, variant="clean_chunk"
        )
    # Highlight best-scoring sentence inside the chunk
    best = max(sents, key=lambda s: _term_overlap(query, s))
    words = cleaned.split()
    if len(words) > max_words:
        cleaned_short = " ".join(words[:max_words]) + "…"
    else:
        cleaned_short = cleaned
    highlighted = highlight_sentences_in_chunk(cleaned_short, [best])
    sel = SelectedSentence(
        text=best,
        filename=str(meta.get("filename") or "document.pdf"),
        page_number=int(meta.get("page_number") or 1),
        chunk_id=str(meta.get("chunk_id") or ""),
        document_id=str(meta.get("document_id") or ""),
        score=_term_overlap(query, best),
        doc_order=0,
        chunk_text=cleaned,
    )
    answer = (
        "**Answer from your documents** (clean_chunk · offline)\n\n" + cleaned_short
    )
    return SentenceAnswer(
        answer=answer,
        sentences=[sel],
        word_count=len(cleaned_short.split()),
        variant="clean_chunk",
        context_chunk=highlighted,
    )


def highlight_sentences_in_chunk(chunk: str, sentences: Sequence[str]) -> str:
    out = chunk or ""
    for s in sentences:
        if s and s in out:
            out = out.replace(s, f">>>{s}<<<", 1)
    return out
