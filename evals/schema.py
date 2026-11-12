"""Question schema loading/validation for evals/data/questions.jsonl."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Literal, Optional, Sequence

CATEGORIES = (
    "factual",
    "paraphrase",
    "exact_identifier",
    "number_or_date",
    "table",
    "multi_hop",
    "multi_document",
    "unanswerable_out_of_domain",
    "unanswerable_near_miss",
    "ambiguous",
)

Split = Literal["tune", "test"]
LabelSource = Literal["draft", "human_verified"]


@dataclass
class GoldItem:
    filename: str
    page: int
    span: str


@dataclass
class Question:
    id: str
    query: str
    category: str
    answerable: bool
    gold: list[GoldItem] = field(default_factory=list)
    key_facts: list[str] = field(default_factory=list)
    split: Split = "test"
    label_source: LabelSource = "draft"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "query": self.query,
            "category": self.category,
            "answerable": self.answerable,
            "gold": [
                {"filename": g.filename, "page": g.page, "span": g.span} for g in self.gold
            ],
            "key_facts": list(self.key_facts),
            "split": self.split,
            "label_source": self.label_source,
            "notes": self.notes,
        }


def _parse_question(obj: dict[str, Any], *, line_no: int) -> Question:
    qid = str(obj.get("id") or "").strip()
    if not qid:
        raise ValueError(f"line {line_no}: missing id")
    query = str(obj.get("query") or "").strip()
    if not query:
        raise ValueError(f"line {line_no}: missing query")
    category = str(obj.get("category") or "").strip()
    if category not in CATEGORIES:
        raise ValueError(f"line {line_no}: invalid category {category!r}")
    if "answerable" not in obj:
        raise ValueError(f"line {line_no}: missing answerable")
    answerable = bool(obj["answerable"])
    split = str(obj.get("split") or "test")
    if split not in ("tune", "test"):
        raise ValueError(f"line {line_no}: split must be tune|test")
    label_source = str(obj.get("label_source") or "draft")
    if label_source not in ("draft", "human_verified"):
        raise ValueError(f"line {line_no}: label_source must be draft|human_verified")
    gold_raw = obj.get("gold") or []
    gold: list[GoldItem] = []
    for g in gold_raw:
        gold.append(
            GoldItem(
                filename=str(g.get("filename") or ""),
                page=int(g.get("page") or 0),
                span=str(g.get("span") or ""),
            )
        )
    if answerable and not gold and label_source == "human_verified":
        raise ValueError(
            f"line {line_no}: human_verified answerable question needs gold spans"
        )
    return Question(
        id=qid,
        query=query,
        category=category,
        answerable=answerable,
        gold=gold,
        key_facts=[str(x) for x in (obj.get("key_facts") or [])],
        split=split,  # type: ignore[arg-type]
        label_source=label_source,  # type: ignore[arg-type]
        notes=str(obj.get("notes") or ""),
    )


def load_questions(path: Path | str) -> list[Question]:
    path = Path(path)
    if not path.is_file():
        return []
    out: list[Question] = []
    for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        obj = json.loads(line)
        out.append(_parse_question(obj, line_no=i))
    return out


def filter_questions(
    questions: Iterable[Question],
    *,
    split: Optional[str] = None,
    verified_only: bool = False,
    categories: Optional[Sequence[str]] = None,
) -> list[Question]:
    rows = list(questions)
    if split:
        rows = [q for q in rows if q.split == split]
    if verified_only:
        rows = [q for q in rows if q.label_source == "human_verified"]
    if categories:
        allow = set(categories)
        rows = [q for q in rows if q.category in allow]
    return rows


def write_questions(path: Path | str, questions: Sequence[Question]) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for q in questions:
            f.write(json.dumps(q.to_dict(), ensure_ascii=False) + "\n")
