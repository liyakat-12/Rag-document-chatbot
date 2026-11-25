# DRAFT LABELS — NOT FOR REPORTING

Generated: 2026-11-14T07:02:30.688017+00:00
Split: `test` · answerable n=51

| Ablation | n | Recall@4 | MRR |
|----------|---|----------|-----|
| faiss_only | 51 | 0.6863 | 0.5098 |
| bm25_only | 51 | 0.5490 | 0.4542 |
| hybrid_rrf | 51 | 0.6667 | 0.5327 |
| hybrid_rrf_normalized_bm25 | 51 | 0.6667 | 0.5327 |
| hybrid_rrf_reranker | 51 | 0.7647 | 0.6536 |
| hybrid_all | 51 | 0.7647 | 0.6536 |

## Answer ablations (DRAFT LABELS — NOT FOR REPORTING)

| Config | n | key_fact_coverage | avg_answer_words |
|--------|---|-------------------|------------------|
| default | 20 | 0.4250 | 124.8 |
| sentence_term_60 | 20 | 0.1000 | 29.9 |
| sentence_term_100 | 20 | 0.1000 | 29.9 |
| sentence_crossencoder_60 | 20 | 0.1500 | 26.9 |
| sentence_crossencoder_100 | 20 | 0.1500 | 26.9 |
| sentence_crossencoder_context_60 | 20 | 0.1500 | 40.0 |
| sentence_crossencoder_context_100 | 20 | 0.1500 | 47.0 |
| clean_chunk | 20 | 0.6500 | 99.3 |
