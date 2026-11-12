# Eval report — default

- Generated: `2026-11-12T14:12:33.980115+00:00`
- Git commit: `a1f86fda9af3c4a48a1c210819df4ce75d19d0ea`
- Corpus hash: `c6f238d861d10cde7f66eb90b1a5af5c17115063c991b598a0ffd1fd7d68d39c`
- Split: `test`
- Questions: 49 (human_verified=0, draft=49)
- Verified-only filter: `False`
- Results JSON: `C:/Users/imabb/RAG_Document_Chatbot/evals/results/20261112_default_test.json`

## Metrics

| Metric | Value |
|--------|-------|
| Recall@1 | 0.1111 |
| Recall@4 | 0.1389 |
| MRR | 0.1204 |
| Precision@4 | 0.0347 |
| hit_rate | 0.1389 |
| not_found_accuracy | 0.7347 |
| refusal_precision | — |
| refusal_recall | 0.0000 |
| false_refusal_rate | 0.0000 |

Latency p50: 14.9 ms · p95: 18.87 ms

### Notes

This run scores retrieval against gold spans. Refusal metrics use empty-retrieval as a proxy; answer-path refusal is Phase 2.

Draft labels are unverified. Headline claims require label_source=human_verified and verified_only=true.
