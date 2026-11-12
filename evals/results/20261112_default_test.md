# Eval report — default

- Generated: `2026-11-12T14:29:07.037309+00:00`
- Git commit: `17638fa207e5dbb3a6dceaaa8bc29a39d2ece25a`
- Corpus hash: `610848afabd8afb55d9792b46b3e31bc3d8a19e392f212d87427f182e06f4494`
- Chunking config hash: `b8896eef7baf7acb`
- Eval index: `C:\Users\imabb\RAG_Document_Chatbot\evals\.index\610848afabd8afb5_b8896eef7baf7acb`
- Uses app index: `False`
- Split: `test`
- Questions: 47 (human_verified=0, draft=47)
- Verified-only filter: `False`
- Results JSON: `C:/Users/imabb/RAG_Document_Chatbot/evals/results/20261112_default_test.json`

## Metrics

| Metric | Value |
|--------|-------|
| Recall@1 | 0.9706 |
| Recall@4 | 1.0000 |
| MRR | 0.9779 |
| Precision@4 | 0.2500 |
| hit_rate | 1.0000 |
| not_found_accuracy | 0.7234 |
| refusal_precision | — |
| refusal_recall | 0.0000 |
| false_refusal_rate | 0.0000 |

Latency p50: 12.51 ms · p95: 21.11 ms

### Notes

Scores retrieval on the isolated eval index built from evals/corpus/. Does not use the app FAISS/BM25 or SQLite.

Draft labels are unverified. Headline claims require label_source=human_verified and verified_only=true.
