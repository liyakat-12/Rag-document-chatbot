# Changelog

All notable changes to DocuMind AI are documented here.
Format inspired by Keep a Changelog. Newest first.

## [Unreleased]

### Added — Phase 1 (evaluation foundation)
- `PROJECT_AUDIT.md` — architecture, feature table, chunk-ID stability, deletion behaviour,
  live refusal examples, risks, later-phase conflicts.
- Span-gold evaluation package under `evals/`:
  - `schema.py`, `span_map.py`, `metrics.py`, `runner.py`, `run.py`, `corpus_util.py`
  - `configs/default.json`
  - `data/questions.jsonl` — **70 draft** questions (`label_source: draft`), tune/test split
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
