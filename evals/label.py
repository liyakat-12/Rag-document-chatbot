"""Interactive labeling helper: python -m evals.label

Keys: v=verify, e=edit in $EDITOR, d=delete, s=skip, q=quit. Saves after each action.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

from evals.corpus_util import find_corpus_pdf, list_corpus_files
from evals.schema import Question, load_questions, write_questions
from evals.span_check import normalize_for_match
from evals.span_map import basename_key, normalize_text

QUESTIONS_PATH = Path(__file__).resolve().parent / "data" / "questions.jsonl"


def _load_page(filename: str, page: int) -> str | None:
    from backend.app.rag.ingest import load_pdf

    match = find_corpus_pdf(filename, subset="all")
    if match is None:
        return None
    pages = load_pdf(match)
    by_page: dict[int, str] = {}
    for i, d in enumerate(pages):
        meta = d.metadata.get("page")
        page_no = int(meta) + 1 if isinstance(meta, int) else i + 1
        by_page[page_no] = d.page_content
    return by_page.get(page)


def _highlight(text: str, span: str) -> str:
    if not text:
        return "(no page text)"
    nt = normalize_for_match(text)
    ns = normalize_for_match(span)
    raw = text
    idx = raw.find(span) if span else -1
    if idx < 0:
        compact = re.sub(r"\s+", " ", raw)
        cspan = re.sub(r"\s+", " ", span)
        cidx = compact.find(cspan)
        if cidx >= 0:
            start = max(0, cidx - 80)
            end = min(len(compact), cidx + len(cspan) + 80)
            snippet = compact[start:end]
            return (
                ("…" if start else "")
                + snippet[: cidx - start]
                + ">>>"
                + snippet[cidx - start : cidx - start + len(cspan)]
                + "<<<"
                + snippet[cidx - start + len(cspan) :]
                + ("…" if end < len(compact) else "")
                + "\n(shown with collapsed whitespace; span normalised match="
                + str(ns in nt)
                + ")"
            )
        return f"(span not found on page; normalised_match={ns in nt})\n--- page start ---\n{raw[:600]}"
    start = max(0, idx - 120)
    end = min(len(raw), idx + len(span) + 120)
    return (
        ("…" if start else "")
        + raw[start:idx]
        + ">>>"
        + raw[idx : idx + len(span)]
        + "<<<"
        + raw[idx + len(span) : end]
        + ("…" if end < len(raw) else "")
    )


def _critical_terms_for_label(query: str) -> list[str]:
    """Critical terms via refusal signal normaliser (names, numbers, codes)."""
    from backend.app.rag.refusal import extract_critical_terms, normalize_for_coverage

    crit = extract_critical_terms(query)
    # Also include longer content tokens that look entity-like
    for t in normalize_for_coverage(query):
        if len(t) >= 4 and t not in crit:
            # keep numbers/codes/% already in crit; add fund-ish tokens
            if any(ch.isdigit() for ch in t) or "/" in t or t.endswith("%"):
                crit.add(t)
    return sorted(crit, key=len, reverse=True)


def scan_corpus_for_critical_terms(query: str) -> list[str]:
    """Search all primary (real) PDFs for critical terms; return every hit with context."""
    from backend.app.rag.ingest import load_pdf
    from backend.app.rag.refusal import normalize_for_coverage

    terms = _critical_terms_for_label(query)
    if not terms:
        return ["(no critical terms extracted)"]

    lines: list[str] = [f"Critical terms: {', '.join(terms[:24])}"]
    hits = 0
    for pdf in list_corpus_files(subset="primary"):
        if pdf.suffix.lower() != ".pdf":
            continue
        try:
            pages = load_pdf(pdf)
        except Exception as exc:
            lines.append(f"{pdf} · load error: {exc}")
            continue
        for i, page in enumerate(pages):
            meta = page.metadata.get("page")
            page_no = int(meta) + 1 if isinstance(meta, int) else i + 1
            toks = set(normalize_for_coverage(page.page_content))
            # also raw lower for multi-token / slash codes
            raw_low = (page.page_content or "").lower()
            matched = [t for t in terms if t in toks or t.lower() in raw_low]
            if not matched:
                continue
            hits += 1
            compact = re.sub(r"\s+", " ", page.page_content or "")
            # Find first matching term context
            ctx = compact[:200]
            for t in matched:
                pos = compact.lower().find(t.lower())
                if pos >= 0:
                    a = max(0, pos - 60)
                    b = min(len(compact), pos + len(t) + 80)
                    ctx = compact[a:b]
                    break
            lines.append(
                f"HIT {pdf.name} p{page_no} · path={pdf} · terms={matched[:6]}\n"
                f"    …{ctx}…"
            )
    if hits == 0:
        lines.append("(no critical-term hits across the 7 real documents — good for unanswerable)")
    else:
        lines.append(f"(total pages with ≥1 critical-term hit: {hits})")
    return lines


def _gold_source_lines(q: Question) -> list[str]:
    out: list[str] = []
    for g in q.gold:
        pdf = find_corpus_pdf(g.filename, subset="all")
        path = str(pdf) if pdf else "(file not found in corpus)"
        out.append(f"GOLD {g.filename} p{g.page} · source_pdf={path}")
        page = _load_page(g.filename, g.page)
        out.append(_highlight(page or "", g.span))
    return out


def _edit_question(q: Question) -> Question:
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "notepad"
    import json

    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        f.write(json.dumps(q.to_dict(), indent=2, ensure_ascii=False))
        path = f.name
    try:
        subprocess.call([editor, path])
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        from evals.schema import _parse_question

        return _parse_question(data, line_no=0)
    finally:
        Path(path).unlink(missing_ok=True)


def run(path: Path = QUESTIONS_PATH) -> int:
    qs = load_questions(path)
    drafts = [i for i, q in enumerate(qs) if q.label_source == "draft"]
    print(f"Loaded {len(qs)} questions · {len(drafts)} drafts to review")
    print("Keys: [v]erify  [e]dit  [d]elete  [s]kip  [q]uit\n")

    for pos, idx in enumerate(drafts):
        q = qs[idx]
        print("=" * 72)
        print(f"[{pos + 1}/{len(drafts)}] id={q.id}  split={q.split}  category={q.category}")
        print(f"query: {q.query}")
        print(f"answerable: {q.answerable}  label_source: {q.label_source}")
        if q.notes:
            print(f"notes: {q.notes}")
        if q.answerable:
            for line in _gold_source_lines(q):
                print(line)
        else:
            print("\nCritical-term scan across all real corpus PDFs (confirm absence):")
            for line in scan_corpus_for_critical_terms(q.query):
                print(" ·", line)

        while True:
            choice = input("\nAction [v/e/d/s/q]: ").strip().lower()
            if choice in {"v", "e", "d", "s", "q"}:
                break
            print("Enter v, e, d, s, or q")

        if choice == "q":
            write_questions(path, qs)
            print("Saved and quit.")
            return 0
        if choice == "s":
            continue
        if choice == "d":
            qs.pop(idx)
            write_questions(path, qs)
            print("Deleted and saved. Restarting remaining drafts…")
            return run(path)
        if choice == "e":
            qs[idx] = _edit_question(q)
            write_questions(path, qs)
            print("Edited and saved.")
            continue
        if choice == "v":
            qs[idx].label_source = "human_verified"
            write_questions(path, qs)
            print("Marked human_verified and saved.")

    write_questions(path, qs)
    counts = Counter(q.label_source for q in qs)
    print("Done.", dict(counts))
    return 0


def main() -> int:
    return run()


if __name__ == "__main__":
    raise SystemExit(main())
