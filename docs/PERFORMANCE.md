# Performance benchmarking

## What is timed

Per chat turn (see `timings` in API response and Analytics UI):

- `cache_lookup_ms`
- `retrieval_ms` (parallel FAISS + BM25 wall clock)
- `faiss_ms` / `bm25_ms` (individual path times)
- `generation_ms`
- `total_ms`

Rolling p50/p95 live in `GET /api/v1/admin/stats` → `latency` (last ~200 samples, in-process).

## Suggested procedure

1. Start backend cold: `uvicorn backend.app.main:app --port 8001`  
2. Upload one PDF (warm embeddings).  
3. Ask the same question twice: first = cold-ish retrieval; second may hit semantic cache.  
4. Record `timings` from the JSON response or Analytics page.  
5. Report machine OS, Python version, `LLM_PROVIDER`, `EMBEDDING_PROVIDER`, and sample size.

## Expected characteristics (qualitative)

- Extractive generation is typically much faster than cloud LLMs.  
- Parallel FAISS+BM25 reduces wall-clock vs sequential when both paths take meaningful time.  
- First request after process start pays FastEmbed / FAISS load cost.
