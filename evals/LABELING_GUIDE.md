# Labeling guide — verifying DocuMind gold questions

This guide is for **you** (the project owner). Agent-drafted questions are always
`label_source: draft` until you change them to `human_verified`.

## Why spans, not chunk IDs

Chunk IDs look like `{document_uuid}_{index}` and **change** when chunk size/overlap
changes. Labels store `(filename, page, span)` copied from extracted page text so they
survive re-chunking. The eval runner maps spans onto whatever chunks exist today.

## How to verify one question

1. Open the source PDF page listed in `gold[].page` (1-indexed, matching DocuMind).
2. Confirm the `span` text appears on that page (whitespace differences are OK; meaning
   and numbers must match).
3. Confirm the question is answerable **from that span** (or from the listed spans).
4. For `key_facts`, each fact should appear in a correct answer.
5. For unanswerable:
   - `unanswerable_out_of_domain` — topic is not in the corpus at all.
   - `unanswerable_near_miss` — related topic exists, but the **specific** fact does not.
6. Set `"label_source": "human_verified"` only after steps 1–5.
7. Keep `split` unchanged unless you are deliberately rebalancing tune/test.

## Split rules

- **tune** (~30%): used later to calibrate refusal thresholds (Phase 2). Never report
  headline portfolio numbers from tune alone.
- **test** (~70%): headline metrics only, and only with `--verified-only`.

## Categories checklist

Ensure coverage across: factual, paraphrase, exact_identifier, number_or_date, table,
multi_hop, multi_document, unanswerable_out_of_domain, unanswerable_near_miss, ambiguous.

Target: ≥15 unanswerable (about half near-miss), ~70 total.

## Current draft status (Phase 1)

| Item | Value |
|------|--------|
| File | `evals/data/questions.jsonl` |
| Total questions | 70 |
| `label_source` | **all `draft` (unverified)** |
| Split | ~21 tune / ~49 test |
| Unanswerable | 18 (8 out-of-domain + 10 near-miss) |
| Corpus | 10 PDFs under `evals/corpus/` (see `manifest.json`) |

Personal/unclear-licence PDFs (resumes, MediAssist, deepfake study) are **gitignored**.
Keep local copies under `evals/corpus/` so spans resolve. Fixture PDFs
(`policy_leave_entitlement.pdf`, `invoice_fixture_q3.pdf`, `api_error_codes.pdf`,
`smoke_ada2.pdf`, `_smoke_perf.pdf`, `qa_design.pdf`) are safe to commit.

## Commands after you verify

```bash
# Count verified
python -c "from evals.schema import load_questions; qs=load_questions('evals/data/questions.jsonl'); print(sum(1 for q in qs if q.label_source=='human_verified'), 'verified of', len(qs))"

# Do NOT freeze a baseline until Phase 2 (and only after ≥40 test questions are verified).
```

## Suggested verification order

1. Fixture docs first (fast, unambiguous numbers/IDs).
2. Smoke resumes (Ada / Grace).
3. Near-miss and out-of-domain (confirm truly unanswerable).
4. MediAssist / deepfake / personal resume questions (check page + exact span).
