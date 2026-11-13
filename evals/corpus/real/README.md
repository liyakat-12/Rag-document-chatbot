# Real (public) primary corpus

Public scheme information documents and SEBI circulars used as the **primary** eval
corpus. Manifest entries record `source_url`, `sha256`, and `pages`.

If you drop additional redistributable PDFs here, re-run:

```bash
python -c "from evals.corpus_util import write_manifest; print(write_manifest())"
```

and extend `evals/data/questions.jsonl` (draft labels only until human verification).
