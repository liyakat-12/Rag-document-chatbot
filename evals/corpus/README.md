# Evaluation corpus

**10 documents** are used for Phase 1 draft labeling (see `manifest.json` for hashes).

## Committed fixtures (safe to share)

| File | Purpose |
|------|---------|
| `policy_leave_entitlement.pdf` | Numbers, table, near-miss stipend |
| `invoice_fixture_q3.pdf` | Invoice totals, SKUs, Tesla near-miss |
| `api_error_codes.pdf` | Exact identifiers (DMAPI-*), HTTP near-miss |
| `smoke_ada2.pdf` | Tiny resume (Ada Lovelace) |
| `_smoke_perf.pdf` | Tiny resume (Grace Hopper) |
| `qa_design.pdf` | Hybrid / RRF fact |

## Local-only (gitignored — keep on disk for draft spans)

| File | Notes |
|------|--------|
| `Liyakat_*.pdf` | Personal resumes — do not publish without consent |
| `MediAssist_*.pdf` | Student project report — licence unclear for redistribution |
| `deepfake_*.pdf` | Study notes — licence unclear |

After adding or removing files:

```bash
python -c "from evals.corpus_util import write_manifest; print(write_manifest())"
```

Regenerate extract cache (optional, for drafting):

```bash
python -c "from pathlib import Path; import json; from langchain_community.document_loaders import PyPDFLoader; ..."
```

or re-run `evals/data/_draft_questions.py` only after `_extracted_pages.json` exists.

## Rules

- Prefer files you have rights to use in a portfolio.
- Unclear-licence files must not be committed; list them in `manifest.json` with origin notes.
- Evaluation runner hashes whatever files are present on disk (`corpus_hash`).
