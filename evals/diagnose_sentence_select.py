"""Diagnose where key facts are lost under sentence-select (DRAFT labels).

For each of N draft questions with key_facts, report whether the fact appears in:
  - default extractive answer
  - retrieved chunk text
  - selected sentences (term mode, fixed splitter)

Loss buckets (when in chunks but not in selected sentences):
  (a) splitting — fact span broken across sentences / missing after split
  (b) scoring — a sentence containing the fact exists but was not picked
  (c) cap — fact sentence was scored into the ranked list but dropped by word cap
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]


def _has_fact(text: str, fact: str) -> bool:
    return bool(fact) and fact.lower() in (text or "").lower()


def _any_fact(text: str, facts: list[str]) -> bool:
    return any(_has_fact(text, f) for f in facts)


def run(*, n: int = 20, split: str = "test") -> dict[str, Any]:
    from langchain_core.messages import HumanMessage

    from backend.app.rag.llm_factory import ExtractiveChatModel
    from backend.app.rag.sentence_select import select_answer_sentences, split_into_sentences
    from evals.eval_index import build_or_load_eval_index, search_eval_index
    from evals.runner import load_config
    from evals.schema import load_questions

    config = load_config("default")
    qpath = ROOT / "evals" / "data" / "questions.jsonl"
    questions = [
        q
        for q in load_questions(qpath)
        if q.split == split and q.answerable and q.key_facts
    ][:n]
    index = build_or_load_eval_index(config, subset="primary")
    top_k = int(config.get("retriever_top_k", 4))

    rows: list[dict[str, Any]] = []
    loss = Counter()
    for q in questions:
        ranked = search_eval_index(index, q.query, top_k=top_k)
        docs = [(d, float(s)) for d, s in ranked.results]
        chunks_text = "\n".join(d.page_content or "" for d, _ in docs)

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
                + f"\n\nUser question: {q.query}\n\n"
                "Write a grounded answer based only on the document context above:"
            )
        )
        default_answer = ExtractiveChatModel._extract_answer([human])

        selected = select_answer_sentences(
            q.query, docs, use_embeddings=False, mode="term", max_words=60
        )
        selected_uncapped = select_answer_sentences(
            q.query, docs, use_embeddings=False, mode="term", max_words=10_000
        )
        selected_text = " ".join(s.text for s in selected.sentences)
        uncapped_text = " ".join(s.text for s in selected_uncapped.sentences)

        all_sents: list[str] = []
        for d, _ in docs:
            all_sents.extend(split_into_sentences(d.page_content or ""))

        facts = list(q.key_facts)
        in_default = _any_fact(default_answer or "", facts)
        in_chunks = _any_fact(chunks_text, facts)
        in_selected = _any_fact(selected_text, facts)
        in_split = _any_fact(" ".join(all_sents), facts)
        fact_sent_exists = any(_any_fact(s, facts) for s in all_sents)
        in_uncapped = _any_fact(uncapped_text, facts)

        loss_type = None
        if in_chunks and not in_selected:
            if not in_split or not fact_sent_exists:
                loss_type = "a_splitting"
            elif not in_uncapped:
                loss_type = "b_scoring"
            else:
                loss_type = "c_cap"
            loss[loss_type] += 1

        rows.append(
            {
                "id": q.id,
                "query": q.query,
                "key_facts": facts,
                "in_default": in_default,
                "in_chunks": in_chunks,
                "in_selected": in_selected,
                "loss": loss_type,
            }
        )

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "label": "DRAFT LABELS — NOT FOR REPORTING",
        "n": len(rows),
        "in_default": sum(1 for r in rows if r["in_default"]),
        "in_chunks": sum(1 for r in rows if r["in_chunks"]),
        "in_selected": sum(1 for r in rows if r["in_selected"]),
        "losses": dict(loss),
        "rows": rows,
    }
    out = ROOT / "evals" / "results" / "_sentence_select_diagnose.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> int:
    report = run()
    print(json.dumps({k: v for k, v in report.items() if k != "rows"}, indent=2))
    for r in report["rows"]:
        print(
            f"{r['id']}: default={r['in_default']} chunks={r['in_chunks']} "
            f"selected={r['in_selected']} loss={r['loss']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
