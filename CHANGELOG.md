# Changelog

All notable changes to DocuMind AI are documented here.
Format inspired by Keep a Changelog. Newest first.

## [Unreleased]

### Changed — Phase 1 fixes round 3 (real primary / synthetic CI)
- Split corpus: `evals/corpus/real/` (primary) vs `evals/corpus/synthetic/` (Phase 4 CI).
  Synthetic manifest entries carry a `SYNTHETIC` notice; questions moved to
  `evals/data/questions_synthetic.jsonl`.
- Primary drafts: **99** questions in `evals/data/questions.jsonl` against real SIDs +
  SEBI circulars (disambiguation / near-miss / paraphrase gates retained).
- `evals.difficulty` now audits real ingestion (Phase 3 backlog), reports hybrid /
  FAISS / BM25 by category, hybrid−FAISS gap, and BM25 miss token examples.
- Eval index hashes **primary** corpus only (`real/`).

### Changed — Phase 1 fixes round 2 (discriminative eval)
- Expanded public/synthetic corpus: 6 near-identical fund SIDs, AMC circular, long
  comparative note (`evals/corpus/_gen_public_fixtures.py` + `download_corpus.py`).
- Rebuilt `evals/data/questions.jsonl` to **108 drafts** (~30/70 tune/test): ≥25%
  document-named disambiguation, multi_document/multi_hop/table/ambiguous floors,
  ≥25 unanswerable (>half near-miss), paraphrase content-word overlap ≤30%.
- Diagnostics: `python -m evals.difficulty` → `evals/DIFFICULTY.md` (chunk ceiling,
  overlap, bm25/faiss ablation). Draft smoke hybrid Recall@4 ≈ **0.84** (was ~1.0).

### Fixed — Phase 1 follow-ups (pre-Phase 2)
- Isolated eval index under `evals/.index/` (never uses app FAISS/BM25/SQLite); results
  record `corpus_hash` + `chunking_config_hash`.
- Removed personal/unclear-licence corpus PDFs and related questions; public fixtures only.
- Labeling CLI: `python -m evals.label` (v/e/d/s/q).
- Span sanity check: `python -m evals.span_check` (0 failures on current drafts).

### Added — Phase 1 (evaluation foundation)
- `PROJECT_AUDIT.md` — architecture, feature table, chunk-ID stability, deletion behaviour,
  live refusal examples, risks, later-phase conflicts.
- Span-gold evaluation package under `evals/`:
  - `schema.py`, `span_map.py`, `metrics.py`, `runner.py`, `run.py`, `corpus_util.py`
  - `configs/default.json`
  - `data/questions.jsonl` — draft questions (`label_source: draft`), tune/test split
  - `LABELING_GUIDE.md`
  - Corpus scaffold + fixtures under `evals/corpus/` (manifest hashed)
- Unit tests: `test_span_map.py`, `test_eval_metrics.py`, `test_eval_schema.py`
- Engineering charter: `.cursor/rules/documind-engineering.mdc`, `docs/ENGINEERING.md`

### Notes
- No retrieval, answering, or UI behaviour changes in Phase 1.
- No baseline metrics reported (Phase 2). Draft labels are **unverified**.

## Prior work (pre-Phase-1 summary)
- Hybrid FAISS + BM25 → RRF, extractive offline answering, citations, semantic cache.
- Streamlit navy/teal UI, honest backend health, About/Analytics.
- Legacy proxy eval: `evals/run_eval.py` + `evals/dataset.json`.
