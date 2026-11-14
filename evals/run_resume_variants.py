"""Run answer variants on the fictional resume fixture (DRAFT / manual)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from langchain_core.documents import Document as LCDocument

ROOT = Path(__file__).resolve().parents[1]
PDF = ROOT / "tests" / "fixtures" / "fictional_resume_jordan_blake.pdf"
QUESTIONS = ROOT / "tests" / "fixtures" / "fictional_resume_questions.jsonl"

VARIANTS = [
    ("default", None, 0),
    ("sentence_term_60", "term", 60),
    ("sentence_term_100", "term", 100),
    ("sentence_crossencoder_60", "crossencoder", 60),
    ("sentence_crossencoder_100", "crossencoder", 100),
    ("sentence_crossencoder_context_60", "crossencoder_context", 60),
    ("sentence_crossencoder_context_100", "crossencoder_context", 100),
    ("clean_chunk", "clean_chunk", 100),
]


def _load_questions() -> list[dict[str, Any]]:
    rows = []
    for line in QUESTIONS.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _chunk_pdf() -> list[tuple[LCDocument, float]]:
    from backend.app.rag.ingest import load_pdf, split_documents

    pages = load_pdf(PDF)
    chunks = split_documents(
        pages,
        document_id="fixture_resume",
        filename=PDF.name,
        file_type="pdf",
    )
    docs = []
    for i, ch in enumerate(chunks):
        meta = dict(ch.metadata or {})
        meta.setdefault("document_id", "fixture_resume")
        meta.setdefault("filename", PDF.name)
        meta.setdefault("chunk_id", f"resume_{i}")
        docs.append((LCDocument(page_content=ch.page_content, metadata=meta), 1.0 - i * 0.01))
    return docs


def _default_answer(query: str, docs: list[tuple[LCDocument, float]]) -> str:
    from langchain_core.messages import HumanMessage

    from backend.app.rag.llm_factory import ExtractiveChatModel

    blocks = []
    for i, (d, _sc) in enumerate(docs, start=1):
        blocks.append(
            f"[Source {i}]\nDocument: {d.metadata.get('filename')}\n"
            f"Page: {d.metadata.get('page_number')}\n"
            f"Content:\n{d.page_content}"
        )
    human = HumanMessage(
        content=(
            "Document context:\n"
            + "\n\n---\n\n".join(blocks)
            + f"\n\nUser question: {query}\n\n"
            "Write a grounded answer based only on the document context above:"
        )
    )
    return ExtractiveChatModel._extract_answer([human])


def run() -> dict[str, Any]:
    from backend.app.rag.sentence_select import select_answer_sentences
    from evals.metrics import key_fact_coverage

    if not PDF.exists():
        from tests.fixtures.gen_resume_fixture import main as gen

        gen()

    questions = _load_questions()
    docs = _chunk_pdf()
    # Retrieve: naive term overlap rank over chunks (fixture is one page)
    def retrieve(query: str) -> list[tuple[LCDocument, float]]:
        scored = []
        qset = {w.lower() for w in query.split() if len(w) > 2}
        for d, base in docs:
            words = {w.lower() for w in (d.page_content or "").split()}
            overlap = len(qset & words) / max(1, len(qset))
            scored.append((d, float(base) + overlap))
        scored.sort(key=lambda x: (-x[1], x[0].metadata.get("chunk_id", "")))
        return scored[:4]

    table: dict[str, Any] = {}
    per_q: list[dict[str, Any]] = []
    for name, mode, max_words in VARIANTS:
        coverages: list[float] = []
        lengths: list[int] = []
        answerable_hits = 0
        answerable_n = 0
        refusal_ok = 0
        refusal_n = 0
        for q in questions:
            ranked = retrieve(q["query"])
            if mode is None:
                answer = _default_answer(q["query"], ranked)
            else:
                selected = select_answer_sentences(
                    q["query"],
                    ranked,
                    use_embeddings=False,
                    mode=mode,  # type: ignore[arg-type]
                    max_words=max_words,
                )
                answer = selected.answer
            lengths.append(len((answer or "").split()))
            facts = list(q.get("key_facts") or [])
            if q.get("answerable"):
                answerable_n += 1
                cov = key_fact_coverage(answer or "", facts) if facts else None
                if cov is not None:
                    coverages.append(cov)
                    if cov > 0:
                        answerable_hits += 1
            else:
                refusal_n += 1
                # Near-miss: prefer not fabricating — soft check for absence of confident false facts
                if "couldn't find" in (answer or "").lower() or len((answer or "").split()) < 40:
                    refusal_ok += 1
            per_q.append(
                {
                    "variant": name,
                    "id": q["id"],
                    "answerable": q.get("answerable"),
                    "answer_preview": (answer or "")[:240],
                    "words": len((answer or "").split()),
                }
            )
        table[name] = {
            "n": len(questions),
            "key_fact_coverage": (sum(coverages) / len(coverages)) if coverages else None,
            "avg_answer_words": (sum(lengths) / len(lengths)) if lengths else None,
            "answerable_hit_rate": (answerable_hits / answerable_n) if answerable_n else None,
            "near_miss_soft_ok": (refusal_ok / refusal_n) if refusal_n else None,
            "label": "DRAFT / MANUAL FIXTURE — NOT FOR REPORTING",
        }

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "fixture": PDF.name,
        "label": "DRAFT / MANUAL FIXTURE — NOT FOR REPORTING",
        "variants": table,
        "answers": per_q,
    }
    out = ROOT / "evals" / "results" / "_resume_fixture_variants.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    report = run()
    print(json.dumps(report["variants"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
