# Evaluation corpus (public / reproducible)

Only documents that can be **committed** or fetched via `download_corpus.py` belong here.
Personal resumes and unclear-licence reports were removed in the Phase 1 fixes.

## Committed fixtures

| File | Purpose |
|------|---------|
| `policy_leave_entitlement.pdf` | Numbers, table, near-miss stipend |
| `invoice_fixture_q3.pdf` | Invoice totals, SKUs, Tesla near-miss |
| `api_error_codes.pdf` | Exact identifiers (DMAPI-*), HTTP near-miss |
| `smoke_ada2.pdf` | Tiny resume (Ada Lovelace) |
| `_smoke_perf.pdf` | Tiny resume (Grace Hopper) |
| `qa_design.pdf` | Hybrid / RRF fact |

## Adding more public PDFs

1. Copy a redistributable PDF into this folder **or** add a URL to `download_corpus.py`.
2. Run `python evals/corpus/download_corpus.py` if using downloads.
3. Regenerate the manifest:

```bash
python -c "from evals.corpus_util import write_manifest; print(write_manifest())"
```

4. Draft or extend questions (`evals/data/_rebuild_public_questions.py` or manually),
   then verify with `python -m evals.label`.

## Isolated index

Evaluation builds FAISS+BM25 under `evals/.index/` (gitignored) from this folder only.
It never reads the app `vector_store/` or SQLite database.
