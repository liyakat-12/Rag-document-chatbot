"""Sanity-check gold spans against extracted page text."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from evals.schema import Question, load_questions
from evals.span_map import basename_key, normalize_text

CORPUS_DIR = Path(__file__).resolve().parent / "corpus"
DEFAULT_QUESTIONS = Path(__file__).resolve().parent / "data" / "questions.jsonl"


def normalize_for_match(text: str) -> str:
    """Whitespace + hyphenation normalisation for span presence checks."""
    t = text or ""
    # Join hyphenated line breaks: "hand -\non" / "hand-\non" → "handon" then spaces
    t = re.sub(r"-\s*\n\s*", "", t)
    t = re.sub(r"-\s+", "", t)  # soft hyphenation leftovers
    return normalize_text(t)


@dataclass
class SpanFailure:
    question_id: str
    filename: str
    page: int
    span: str
    reason: str


def _page_text(filename: str, page: int, cache: dict[str, list[str]]) -> Optional[str]:
    key = basename_key(filename)
    if key not in cache:
        # find matching corpus file
        match = None
        for p in CORPUS_DIR.glob("*.pdf"):
            if basename_key(p.name) == key:
                match = p
                break
        if match is None:
            cache[key] = []
            return None
        from backend.app.rag.ingest import load_pdf

        pages = load_pdf(match)
        # load_pdf already cleans; page_number in gold is 1-indexed
        cache[key] = [d.page_content for d in pages]
    pages = cache[key]
    if page < 1 or page > len(pages):
        return None
    return pages[page - 1]


def check_question_spans(q: Question, cache: Optional[dict[str, list[str]]] = None) -> list[SpanFailure]:
    cache = cache if cache is not None else {}
    failures: list[SpanFailure] = []
    if not q.answerable:
        return failures
    if not q.gold:
        failures.append(
            SpanFailure(q.id, "", 0, "", "answerable question has empty gold list")
        )
        return failures
    for g in q.gold:
        text = _page_text(g.filename, g.page, cache)
        if text is None:
            failures.append(
                SpanFailure(
                    q.id,
                    g.filename,
                    g.page,
                    g.span,
                    "file missing from corpus or page out of range",
                )
            )
            continue
        if not g.span.strip():
            failures.append(
                SpanFailure(q.id, g.filename, g.page, g.span, "empty span")
            )
            continue
        page_n = normalize_for_match(text)
        span_n = normalize_for_match(g.span)
        if span_n not in page_n:
            failures.append(
                SpanFailure(
                    q.id,
                    g.filename,
                    g.page,
                    g.span,
                    "span not found on page after whitespace/hyphen normalisation",
                )
            )
    return failures


def check_all(
    questions_path: Path | str = DEFAULT_QUESTIONS,
) -> list[SpanFailure]:
    qs = load_questions(questions_path)
    cache: dict[str, list[str]] = {}
    out: list[SpanFailure] = []
    for q in qs:
        out.extend(check_question_spans(q, cache))
    return out


def main() -> int:
    failures = check_all()
    print(f"span_check failures: {len(failures)}")
    for f in failures:
        print(f"- [{f.question_id}] {f.filename} p{f.page}: {f.reason}")
        print(f"  span={f.span[:120]!r}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
