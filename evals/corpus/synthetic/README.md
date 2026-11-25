# Synthetic corpus (Phase 4 CI fixture)

**These documents are generated, fictional, and not real fund, regulatory, or personal
data.** Scheme names such as Aurora / Boreal / Cascade, ISINs, TERs, and circular IDs
are invented for DocuMind evaluation only.

## Purpose

- Fast, redistributable offline fixture for CI (wired in Phase 4).
- Near-identical SIDs exercise document-scoped disambiguation without depending on
  live AMC downloads.

## Contents

- Tiny resumes, leave policy, invoice, API errors, QA note
- Six synthetic fund SIDs (`scheme_amgf*.pdf`, `scheme_bfcf*.pdf`, `scheme_cldf*.pdf`)
- Synthetic AMC circular + comparative note

Regenerate with:

```bash
python evals/corpus/synthetic/_gen_public_fixtures.py
# or
python evals/corpus/download_corpus.py
```

Questions for this tree live in `evals/data/questions_synthetic.jsonl`.
The primary eval set is `evals/data/questions.jsonl` against `evals/corpus/real/`.
