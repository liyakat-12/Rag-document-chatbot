# Unattended session 1 report

**Branch:** `unattended-1` (from `phase-1-eval-foundation`)  
**Summary:** All four tasks completed behind default-off flags (except LLM injection
guard, which is on for LLM providers only and does not affect extractive). Default
behaviour snapshot regression **passed**. No Phase 2 baseline freeze. No headline
metrics. Questions.jsonl untouched.

| Task | Status |
|------|--------|
| 0 Snapshot lock | **done** |
| 1 Refusal engine | **done** |
| 2 Retrieval extras + ablation | **done** (eval-index normalized BM25 is approximate — see DECISIONS) |
| 3 Citations + injection | **done** |
| 4 CI + lifecycle + upload | **done** |

---

## Task 0 — Behaviour snapshot

**Status:** done  
**Files:** `evals/build_behaviour_snapshot.py`, `evals/results/_default_behaviour_snapshot.json`,
`tests/regression/test_default_behaviour.py`, `docs/DECISIONS.md`  
**Tests:** snapshot regression **1 passed** (this session)  
**Decisions:** [DECISIONS.md — Behaviour snapshot source](DECISIONS.md)

## Task 1 — Refusal engine

**Status:** done  
**Files:** `backend/app/rag/refusal.py`, `backend/app/config.py` (flags),
`backend/app/services/chat_service.py` (wire-up when enabled),
`backend/app/rag/semantic_cache.py` (refusal hash in cache key),
`evals/calibrate_refusal.py`, `tests/unit/test_refusal.py`  
**Tests:** `test_refusal.py` **7 passed**  
**Notes:** All cutoffs marked UNCALIBRATED; `refusal_enabled` defaults false so
snapshot unchanged.  
**Unverified:** Real UX of weak_evidence/not_found copy in Streamlit UI (API meta only).

## Task 2 — Retrieval components + ablation

**Status:** done (with documented limitation)  
**Files:** `backend/app/rag/reranker.py`, `dedupe.py`, hybrid_search hooks,
`evals/ablation_runner.py`, `evals/results/_draft_ablation.md`,
`tests/unit/test_retrieval_extras.py`  
**Tests:** `test_retrieval_extras.py` **4 passed**  
**Draft smoke (NOT FOR REPORTING):** hybrid_rrf Recall@4 ≈ 0.67; with reranker ≈ 0.76
on draft test split (n=51 answerable).  
**Decisions:** [Eval-index BM25 tokenizer](DECISIONS.md), [Reranker dependency](DECISIONS.md)  
**Remaining:** Wire normalized tokenizer into eval-index BM25 rebuild for true
`hybrid_rrf_normalized_bm25` ablation parity.

## Task 3 — Citations + injection defence

**Status:** done  
**Files:** `backend/app/rag/citations.py`, `qa_chain.py` (guard), `SECURITY.md`,
`tests/fixtures/inject_*.pdf`, `tests/unit/test_injection_guard.py`, metrics helpers  
**Tests:** `test_injection_guard.py` **5 passed**  
**Notes:** `citations_validate` default off; guard skipped for extractive (snapshot OK).

## Task 4 — CI, lifecycle, upload safety

**Status:** done  
**Files:** `.github/workflows/ci.yml`, `evals/ci_smoke_synthetic.py`,
`evals/configs/ci_thresholds.json`, `backend/app/rag/content_hash.py`,
`document_service.py`, `utils/security.py`, `tests/unit/test_upload_and_lifecycle.py`  
**Tests:** upload/lifecycle tests **passed** in unit run; synthetic CI smoke
Recall@4=0.80 / nfa=0.74 vs floors 0.75 / 0.60 → **pass**  
**Unverified:** First real GitHub Actions run (workflow YAML validated locally with PyYAML).

---

## Final verification (this session)

- `pytest tests -q -m "not slow"` → **69 passed**, 1 deselected  
- `pytest tests/regression/test_default_behaviour.py` → **1 passed**  
- Synthetic CI smoke → **pass**  
- Questions.jsonl / gold labels → **not modified**

## Remaining work (not started)

- Human verification of draft questions; then calibrate refusal on tune  
- Freeze Phase 2 baseline  
- Eval-index normalized BM25 rebuild for ablation parity  
- Streamlit UX for weak_evidence / possibly-related passages
