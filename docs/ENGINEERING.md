# DocuMind AI — Project Context and Engineering Rules

Human-readable copy of the project charter. Cursor always-on rule:
`.cursor/rules/documind-engineering.mdc`.

See the full upgrade prompt (phases 1–7) and evaluation integrity rules in that file
and in `PROJECT_AUDIT.md` / `CHANGELOG.md`.

## Must preserve
Offline extractive mode, hybrid FAISS+BM25+RRF, citations, document-scoped retrieval
(+ cache keys), semantic cache, diagnostics, latency analytics, `/health`, FastAPI/
Streamlit split, navy/teal UI.

## Evaluation integrity
Never invent metrics. Draft labels are `label_source: draft`. Headline numbers only from
`human_verified` test-split results files. Gold = `(filename, page, span)`.

## Session end
Update `CHANGELOG.md`, stop at a stable commit, write a phase report, wait for
`continue` before the next phase.
