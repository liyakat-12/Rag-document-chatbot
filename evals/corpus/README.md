# Evaluation corpus

Split into two trees:

| Path | Role |
|------|------|
| `real/` | **Primary** eval corpus (public SIDs + SEBI circulars) |
| `synthetic/` | Generated / fictional fixtures for **Phase 4 CI** |

Questions:

- Primary drafts: `evals/data/questions.jsonl`
- Synthetic drafts: `evals/data/questions_synthetic.jsonl`

The isolated eval index (`evals/.index/`) indexes **`real/` only** by default.

## Manifest

```bash
python -c "from evals.corpus_util import write_manifest; print(write_manifest())"
# or
python evals/corpus/download_corpus.py
```

Each synthetic entry includes a `synthetic_notice`. Real entries include `source_url`,
`sha256`, and `pages` (fill any blank source URLs you can confirm).

## Adding more real PDFs

1. Drop redistributable PDFs into `real/`.
2. Add provenance to `KNOWN_REAL_META` in `evals/corpus_util.py` when known.
3. Refresh the manifest and extend `questions.jsonl` (draft labels only).
