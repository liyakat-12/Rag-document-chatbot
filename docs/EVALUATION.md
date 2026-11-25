# Evaluation guide

## Commands

```bash
# Local retrieval proxy metrics (needs a non-empty FAISS index)
python -m evals.run_eval

# Live API groundedness checks (start backend first)
python -m evals.run_eval --api --base http://127.0.0.1:8001/api/v1 --out evals/last_report.json
```

## Metric definitions

| Name | Definition | Limitation |
|------|------------|------------|
| `keyword_hit_rate` | Fraction of cases where any `relevant_keywords` appear in concatenated top-k chunk text | Proxy — not gold-chunk Recall@K |
| Retrieval latency | Wall-clock of `hybrid_search_detailed` | Cold start includes embedding model load |
| API `pass_rate` | Fraction of cases matching `expected_answer_contains` / not-found rules | Depends on indexed corpus content |
| Cache hit rate | `cache_hits / (hits+misses)` from admin stats | Process-local counters |

**Unavailable without gold labels:** Recall@K, MRR, citation exact-match F1.

## Honesty rule

Never publish fabricated Recall@K / MRR. Prefer keyword_hit_rate + latency + qualitative citation checks until a gold set exists.
