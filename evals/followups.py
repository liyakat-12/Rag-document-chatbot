"""Load and evaluate two-turn follow-up drafts (label_source: draft)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from backend.app.rag.followups import rewrite_followup_offline
from evals.eval_index import build_or_load_eval_index, search_eval_index
from evals.metrics import mrr, recall_at_4
from evals.runner import load_config
from evals.span_map import GoldSpan, ranks_of_relevant

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FOLLOWUPS = Path(__file__).resolve().parent / "data" / "questions_followups.jsonl"


@dataclass
class FollowupPair:
    id: str
    turn1: str
    turn2: str
    category: str
    answerable: bool
    gold: list[dict[str, Any]] = field(default_factory=list)
    key_facts: list[str] = field(default_factory=list)
    split: str = "test"
    label_source: str = "draft"
    notes: str = ""


def load_followups(path: Path | str = DEFAULT_FOLLOWUPS) -> list[FollowupPair]:
    p = Path(path)
    if not p.is_file():
        return []
    out: list[FollowupPair] = []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line:
            continue
        obj = json.loads(line)
        out.append(
            FollowupPair(
                id=str(obj["id"]),
                turn1=str(obj["turn1"]),
                turn2=str(obj["turn2"]),
                category=str(obj.get("category") or "factual"),
                answerable=bool(obj.get("answerable", True)),
                gold=list(obj.get("gold") or []),
                key_facts=list(obj.get("key_facts") or []),
                split=str(obj.get("split") or "test"),
                label_source=str(obj.get("label_source") or "draft"),
                notes=str(obj.get("notes") or ""),
            )
        )
    return out


def evaluate_followups(
    *,
    path: Path | str = DEFAULT_FOLLOWUPS,
    split: Optional[str] = None,
    config_name: str = "default",
) -> dict[str, Any]:
    """Rewrite turn2 offline, retrieve with rewritten query, score vs gold (draft OK)."""
    pairs = load_followups(path)
    if split:
        pairs = [p for p in pairs if p.split == split]
    config = load_config(config_name)
    index = build_or_load_eval_index(config)
    top_k = int(config.get("retriever_top_k", 4))
    min_ov = float(config.get("span_min_overlap", 0.5))

    cases = []
    r4s: list[float] = []
    for pair in pairs:
        rewrite = rewrite_followup_offline(pair.turn2, [pair.turn1])
        ranked = search_eval_index(index, rewrite.rewritten, top_k=top_k)
        gold = [
            GoldSpan(str(g["filename"]), int(g["page"]), str(g.get("span") or ""))
            for g in pair.gold
        ]
        ranks = ranks_of_relevant(gold, ranked, min_overlap=min_ov) if gold else []
        r4 = recall_at_4(ranks) if gold else None
        if r4 is not None:
            r4s.append(r4)
        cases.append(
            {
                "id": pair.id,
                "turn1": pair.turn1,
                "turn2": pair.turn2,
                "rewritten": rewrite.rewritten,
                "rewrite_method": rewrite.method,
                "entities_carried": rewrite.entities_carried,
                "skipped_reason": rewrite.skipped_reason,
                "label_source": pair.label_source,
                "Recall@4": r4,
                "MRR": mrr(ranks) if gold else None,
            }
        )

    return {
        "label": "DRAFT LABELS — NOT FOR REPORTING",
        "n": len(cases),
        "n_human_verified": sum(1 for p in pairs if p.label_source == "human_verified"),
        "mean_Recall@4": (sum(r4s) / len(r4s)) if r4s else None,
        "cases": cases,
    }


def main() -> int:
    report = evaluate_followups()
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
