# Eval report — default

- Generated: `2026-11-13T06:35:59.428561+00:00`
- Git commit: `b5eed4106c3fb3e6e0e5b9bc5c3899b29e6a677a`
- Corpus hash: `136f9e86dcc51157b4089c5d6a240a2f143d5431408ab12444d3306a91a16ab3`
- Chunking config hash: `b8896eef7baf7acb`
- Eval index: `C:\Users\imabb\RAG_Document_Chatbot\evals\.index\136f9e86dcc51157_b8896eef7baf7acb`
- Uses app index: `False`
- Split: `test`
- Questions: 71 (human_verified=0, draft=71)
- Verified-only filter: `False`
- Results JSON: `C:/Users/imabb/RAG_Document_Chatbot/evals/results/20261113_default_test.json`

## Metrics

| Metric | Value |
|--------|-------|
| Recall@1 | 0.4314 |
| Recall@4 | 0.6667 |
| MRR | 0.5327 |
| Precision@4 | 0.1814 |
| hit_rate | 0.6667 |
| not_found_accuracy | 0.7183 |
| refusal_precision | — |
| refusal_recall | 0.0000 |
| false_refusal_rate | 0.0000 |

Latency p50: 27.29 ms · p95: 41.34 ms

### Notes

Scores retrieval on the isolated eval index built from evals/corpus/. Does not use the app FAISS/BM25 or SQLite.

Draft labels are unverified. Headline claims require label_source=human_verified and verified_only=true.
