# Decisions log (unattended sessions)

## 2026-11-13 — Behaviour snapshot source

**Decision:** Snapshot default retrieval + extractive answers against the isolated
**primary eval index** (`evals/corpus/real/`), not the live app `vector_store/`.

**Alternatives:** (a) require uploading all real PDFs into the app store; (b) mock
empty retrieval.

**Reason:** The 99 draft questions target the real primary corpus. The app store is
user-local and may be empty in CI. The eval index already mirrors production hybrid
RRF parameters (FAISS + BM25, weight 0.5, dense floor 0.22). Snapshot uses
`search_eval_index(..., top_k=10)` plus `ExtractiveChatModel` via `generate_answer`
with `LLM_PROVIDER=extractive` so answers/citations match the offline default path.

## 2026-11-13 — Config flags for new features

**Decision:** Add feature flags on `Settings` (env-backed) all defaulting to current
behaviour (`refusal.enabled=false`, retrieval extras off, `citations.validate=false`).
`llm.injection_guard` defaults **on** for non-extractive LLM providers only; extractive
path skips the guard so the snapshot stays stable.

**Alternatives:** JSON feature file; always-on with no flags.

**Reason:** Phase 2 baseline must still measure the original system; flags keep
defaults unchanged.

## 2026-11-13 — Eval-index ablation BM25 tokenizer

**Decision:** Eval-index ablations labelled `hybrid_rrf_normalized_bm25` /
`hybrid_all` still use the eval index's whitespace BM25 posting lists for this
session; normalized tokenization is fully wired in the **app** hybrid path
(`retrieval.bm25_tokenizer`). Document the gap rather than rebuild a second
eval BM25 index mid-session.

**Alternatives:** Duplicate eval BM25 with normalized tokens now.

**Reason:** Rebuilding 3013-chunk embeddings/BM25 twice risked hanging the
unattended session; app-path unit tests cover the normalized tokenizer.

## 2026-11-13 — Reranker dependency

**Decision:** Lazy-load `sentence_transformers.CrossEncoder`; on ImportError or
load failure, warn and fall back to RRF order (no hard dependency for default
offline CI).

**Reason:** CI must run offline with no model download when the flag is off;
when the flag is on in CI without the model, behaviour degrades safely.

## 2026-11-13 — Citation viewer match order (Unattended-2)

**Decision:** Highlight path is exact `page.search_for` → whitespace/hyphen
normalised word-box map → best text-block by token Jaccard (≥0.15) → chunk-text
fallback with `>>>span<<<` markers. Page PNGs cached under `data/page_cache/`
keyed by path+mtime+page+span+dpi. Dependency: `pymupdf>=1.24,<2.2`.

**Alternatives:** Always re-render; PDF.js in browser; store highlight quads at ingest.

**Reason:** Works offline in Streamlit without a JS PDF stack; cache keeps
rerenders cheap; fallbacks cover noisy PDF text extraction.
