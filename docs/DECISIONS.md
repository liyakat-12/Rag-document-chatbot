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
