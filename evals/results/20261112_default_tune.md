# Eval report — default

- Generated: `2026-11-12T14:35:36.460453+00:00`
- Git commit: `124c060231ec0450dbf68625b216f1cbcd2cb2bd`
- Corpus hash: `3eca4ae9ce9177a4aa450637ced7c55beff0a0065efa5426f9c34d1103d1803d`
- Chunking config hash: `b8896eef7baf7acb`
- Eval index: `C:\Users\imabb\RAG_Document_Chatbot\evals\.index\3eca4ae9ce9177a4_b8896eef7baf7acb`
- Uses app index: `False`
- Split: `tune`
- Questions: 32 (human_verified=0, draft=32)
- Verified-only filter: `False`
- Results JSON: `C:/Users/imabb/RAG_Document_Chatbot/evals/results/20261112_default_tune.json`

## Metrics

| Metric | Value |
|--------|-------|
| Recall@1 | 0.5417 |
| Recall@4 | 0.9167 |
| MRR | 0.6910 |
| Precision@4 | 0.2708 |
| hit_rate | 0.9167 |
| not_found_accuracy | 0.7500 |
| refusal_precision | — |
| refusal_recall | 0.0000 |
| false_refusal_rate | 0.0000 |

Latency p50: 19.6 ms · p95: 25.06 ms

### Notes

Scores retrieval on the isolated eval index built from evals/corpus/. Does not use the app FAISS/BM25 or SQLite.

Draft labels are unverified. Headline claims require label_source=human_verified and verified_only=true.
