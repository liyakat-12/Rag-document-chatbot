# Eval report — default

- Generated: `2026-11-12T14:35:37.236891+00:00`
- Git commit: `124c060231ec0450dbf68625b216f1cbcd2cb2bd`
- Corpus hash: `3eca4ae9ce9177a4aa450637ced7c55beff0a0065efa5426f9c34d1103d1803d`
- Chunking config hash: `b8896eef7baf7acb`
- Eval index: `C:\Users\imabb\RAG_Document_Chatbot\evals\.index\3eca4ae9ce9177a4_b8896eef7baf7acb`
- Uses app index: `False`
- Split: `test`
- Questions: 76 (human_verified=0, draft=76)
- Verified-only filter: `False`
- Results JSON: `C:/Users/imabb/RAG_Document_Chatbot/evals/results/20261112_default_test.json`

## Metrics

| Metric | Value |
|--------|-------|
| Recall@1 | 0.5000 |
| Recall@4 | 0.8036 |
| MRR | 0.6339 |
| Precision@4 | 0.2054 |
| hit_rate | 0.8036 |
| not_found_accuracy | 0.7368 |
| refusal_precision | — |
| refusal_recall | 0.0000 |
| false_refusal_rate | 0.0000 |

Latency p50: 18.31 ms · p95: 27.92 ms

### Notes

Scores retrieval on the isolated eval index built from evals/corpus/. Does not use the app FAISS/BM25 or SQLite.

Draft labels are unverified. Headline claims require label_source=human_verified and verified_only=true.
