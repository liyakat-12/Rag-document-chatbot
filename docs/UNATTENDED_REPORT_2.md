# Unattended session 2 report

**Branch:** `unattended-2` (from `phase-2-baseline-refusal`)  
**Summary:** Tasks 0–4 completed. Default retrieval/answering unchanged (flags
default off). `questions.jsonl` untouched. No baseline freeze, calibration, or
headline metrics. Snapshot regression passed as part of the full suite.

| Task | Status |
|------|--------|
| 0 Labeling support | **done** |
| 1 Citation viewer | **done** |
| 2 Chat polish + eval analytics | **done** |
| 3 Ingest quality flags | **done** |
| 4 Docker | **files done; Docker CLI unavailable — not built/run** |

**Final tests (this session):** `pytest tests -q` → **92 passed** in ~61s  
(includes `tests/regression/test_default_behaviour.py`).

---

## Task 0 — Labeling support

**Status:** done  

### Tune unanswerable counts (existing `questions.jsonl`, untouched)

| Kind | Count |
|------|------:|
| `unanswerable_near_miss` | 5 |
| `unanswerable_out_of_domain` | 3 |
| **Total** | **8** |

Fewer than 12 → drafted **5** additions in
`evals/data/questions_tune_additions.jsonl` (`label_source: draft`): 4 near-miss +
1 out-of-domain → **13** if merged (user reviews/merges).

**Files:** `evals/label.py`, `evals/data/questions_tune_additions.jsonl`,
`tests/unit/test_label_scan.py`  
**Tests:** `test_label_scan.py` **3 passed** (earlier this session) + suite  
**Decisions:** none beyond drafting into a side file (not editing `questions.jsonl`)

---

## Task 1 — Citation viewer with span highlighting

**Status:** done  

**Files:** `backend/app/rag/page_viewer.py`, `backend/app/api/documents.py`
(`/{id}/pages/{n}`, `/{id}/meta`), `streamlit_app/components/citation_viewer.py`,
`sources.py`, `documents.py`, `chat.py`, `api_client.py`,
`tests/unit/test_page_viewer.py`, `requirements.txt` (`pymupdf`)  

**Tests:** `test_page_viewer.py` **8 passed** — exact (real Motilal/HDFC corpus),
line-broken normalised, hyphenated, block fallback, chunk-text fallback, cache hit  

**Decisions:** [Citation viewer match order](DECISIONS.md)

### Manual UI check steps (cannot render UI in this session)

1. Start backend + Streamlit; upload or use an indexed real SID PDF.
2. Ask a grounded question; open **Supporting evidence**.
3. Click **Open in viewer** on a source → page PNG appears with teal highlight;
   caption shows match mode (`exact` / `normalized` / `block`).
4. Use **Prev/Next** — span clears when browsing other pages; **Close viewer** dismisses.
5. Force a nonsense span (or use a source whose text was heavily cleaned) → expect
   `chunk_fallback` info + `>>>span<<<` in chunk text.
6. **Documents** → expand **Metadata & page preview** → flip pages; confirm status,
   page/chunk counts; after enabling `INGEST_FLAG_LOW_TEXT_PAGES` and re-upload,
   low-text warning may appear (flag default off).

**Unverified:** Visual alignment of highlight rectangles on every real PDF layout;
Streamlit image sharpness at DPI 144.

---

## Task 2 — Chat polish and evaluation analytics

**Status:** done  

**Files:** `streamlit_app/components/chat.py`, `analytics.py`,
`evals/results_browser.py`, `tests/unit/test_eval_analytics.py`  

**Tests:** `test_eval_analytics.py` **7 passed** — empty-state copy, real
`evals/results/` load, draft warning / `human_verified=0` on dated runs, ablation
draft flag, synthetic verified not-draft  

### Manual UI check steps

1. **Chat:** with `REFUSAL_ENABLED=false` (default) — no status badge from refusal
   meta; **Copy answer**, **Regenerate**, **Clear conversation** work; errors show
   friendly text without stack traces.
2. Enable refusal in `.env`, restart, ask OOD question → badge **Not found** /
   **Weak evidence** with reason caption.
3. **Analytics → Live usage:** latency/cache labelled as live; not mixed with eval.
4. **Evaluation results:** latest dated JSON metrics each show
   `human_verified=…` and **draft labels** warning; ablation table warns draft;
   date filter narrows history; empty dir (or rename results away) shows how-to-run
   empty state. Confirm **no** “sample numbers” / demo placeholders.

**Unverified:** Live Streamlit layout density on narrow viewports.

---

## Task 3 — Ingestion quality flags

**Status:** done  

**Files:** `backend/app/rag/ingest.py`, `backend/app/config.py`,
`document_service.py` (`.meta.json` sidecar for low-text),
`evals/eval_index.py` (hash), `evals/ablation_runner.py` (`INGEST_ABLATIONS`),
`tests/unit/test_ingest_quality.py`  

**Tests:** `test_ingest_quality.py` **5 passed** — synthetic multi-page header
detection, strip keeps body, once-only lines kept, low-text flagging, hash changes
only when flags on  

**Decisions:** [Ingest quality flags and eval index hash](DECISIONS.md)  

**Verified:** Default-off hash equals prior payload (no rebuild of default index).
Enabled flags → different `chunking_config_hash` → separate `evals/.index/` dir.

**Not run:** Ingest ablations against real/draft labels (registered only).

---

## Task 4 — Docker

**Status:** files complete; **runtime not verified**  

**Files:** `Dockerfile`, `docker-compose.yml` (`api` + `ui`), `.dockerignore`,
`.env.example` (offline defaults, optional `.env`), volumes
`documind_uploads|vectors|data|models`, healthchecks, `PRELOAD_MODELS` build-arg  

**What was run:** `docker --version` / `docker compose version` → **Docker CLI not
installed / not on PATH** on this Windows host. **Did not** build or `compose up`.
**Do not claim** the stack runs until executed on a machine with Docker.

**Decisions:** [Docker offline defaults](DECISIONS.md)

---

## Commits on `unattended-2`

1. `68c0ab2` Improve labeling CLI and draft tune unanswerable additions  
2. `2e7ca64` Add citation page viewer with PyMuPDF span highlighting  
3. `7ce5e48` Polish chat UX and add evaluation analytics from evals/results  
4. `1fdffe0` Add default-off ingest header strip and low-text page flags  
5. `8f98c6f` Ship offline Docker Compose stack with model cache volumes  
6. *(this report + CHANGELOG commit)*

---

## Remaining work

- Human review/merge of `questions_tune_additions.jsonl`; continue labeling
  (`human_verified`) before Phase 2 baseline/calibration.
- Run Docker Compose on a host with Docker; optionally `PRELOAD_MODELS=1`.
- Manual UI pass for citation highlights + analytics draft banners.
- Execute ingest ablations only after verified baseline (separate index dirs).
