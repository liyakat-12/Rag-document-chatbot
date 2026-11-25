# Question file

`questions.jsonl` — one JSON object per line.

## Required fields

| Field | Type | Notes |
|-------|------|--------|
| `id` | string | Stable id, e.g. `factual_001` |
| `query` | string | User question |
| `category` | string | One of the categories in `evals/schema.py` |
| `answerable` | bool | False for out-of-domain / near-miss / ambiguous-unanswerable |
| `gold` | list | `{filename, page, span}` — exact text from extracted PDF |
| `key_facts` | list[str] | Short strings that should appear in a good answer |
| `split` | `tune` \| `test` | Tune ≈ 30%, test ≈ 70%, stratified by category |
| `label_source` | `draft` \| `human_verified` | Agent drafts are always `draft` |
| `notes` | string | Optional |

## Integrity

- Never mark `human_verified` until you have checked the span in the PDF yourself.
- Headline metrics in docs/UI must use `--verified-only` on the **test** split.
- See `evals/LABELING_GUIDE.md`.
