# DocuMind AI — Project status

Generated: 2026-11-14 (local). Read-only audit except this file.  
Working tree: branch **`chat-screen`** with substantial **uncommitted** UI/answer-quality edits on tip `f061ed7`.

## 1. Branches

| Branch | Tip | Merged into `main`? | One-line contents |
|--------|-----|---------------------|-------------------|
| `main` | `a1f86fda9af3c4a48a1c210819df4ce75d19d0ea` | — (is main) | Improve RAG pipeline and Streamlit interface |
| `phase-1-eval-foundation` | `21fa49e49f54db37d6223c3daf8cef4232fa88c1` | no | Real corpus primary; synthetic parked for CI |
| `phase-2-baseline-refusal` | `c00f59ddb251d6713fc3b0dc7ba31baa6718e831` | no | Same tip as unattended-1 (refusal / snapshot / flags) |
| `unattended-1` | `c00f59ddb251d6713fc3b0dc7ba31baa6718e831` | no | Snapshot, refusal flag, retrieval extras, CI smoke |
| `unattended-2` | `95bbc98651672b185cf1e2625b926b337665130e` | no | Labeling, citation viewer, Docker Compose, ingest flags |
| `unattended-3` | `f061ed730a85766ec6347354cda47cb79dfe4123` | no | Sentence-select + hyphenation flags (default off) |
| `unattended-3-docx-wip` | `051e1be8880998bd337086b398be02b20c3f171e` | no | WIP DOCX ingest / section citations |
| `answer-quality` | `f061ed730a85766ec6347354cda47cb79dfe4123` | no | Same committed tip as unattended-3; quality WIP mostly uncommitted on `chat-screen` |
| `chat-screen` | `f061ed730a85766ec6347354cda47cb79dfe4123` + dirty WT | no | UI redesign / dark-mode tokens (uncommitted) |

**App running from:** git checkout is **`chat-screen`**. Persistent API on `:8001` was **unreachable** at audit time. A temporary uvicorn on `:8019` was started only for timing (see §9); no Streamlit process verified.

## 2. What runs on `main` today

Pages (Streamlit): **Chat**, **Documents**, **Analytics**, **Settings**, **About**.  
User can: upload PDFs, index, ask grounded questions (LLM or extractive), see citations/sources, history, feedback, export PDF, view analytics, change dark mode / read settings. Hybrid FAISS+BM25→RRF.  
`main` does **not** include later unattended sentence-select / chat-screen UI commits (those are on other branches / dirty WT).

## 3. Feature flags

Defaults from `backend/app/config.py` (local `.env` overrides noted).

| Flag | Default | Safe to turn on? |
|------|---------|------------------|
| `semantic_cache_enabled` | true | Yes (already on); exact-hash cache |
| `semantic_cache_similarity` | false | Caution — slower miss path |
| `refusal_enabled` | false | **No for demo claims** — thresholds marked UNCALIBRATED; 0 verified tune labels |
| `retrieval_bm25_tokenizer=normalized` | whitespace | Caution — changes retrieval vs snapshot |
| `retrieval_reranker_enabled` | false | Caution — model download/latency; draft Recall↑ but unverified |
| `retrieval_exact_match_boost` | false | Caution — draft ablations only |
| `retrieval_dedupe_near_duplicates` | false | Caution — draft only |
| `citations_validate` | false | Caution — may drop/alter cites |
| `ingest_strip_repeated_headers_footers` | false | Caution — **changes index hash** |
| `ingest_flag_low_text_pages` | false | Caution — index hash / metadata |
| `chat_rewrite_followups` | false | Caution — changes query rewrite vs snapshot |
| `answer_sentence_select` | false | Caution — draft key-fact often **worse** except `clean_chunk` |
| `answer_sentence_select_mode` | term | Use only with select on; see §4 |
| `ingest_fix_hyphenation` | false | Caution — **changes chunk text / index hash** |
| `ui_developer_mode` | false | Yes for operators; shows scores |
| `llm_injection_guard` | true | Yes (LLM providers); extractive unaffected |

Local `.env` (non-secret): `LLM_PROVIDER=extractive`, `EMBEDDING_PROVIDER=local`, `DEBUG=false`. `OPENAI_API_KEY` is set locally (gitignored).

## 4. Answer quality

- **Current mode (local settings):** extractive; `answer_sentence_select=false` → classic full-chunk extractive.
- **Exists (on unattended-3 / dirty WT):** sentence select, modes `term` / `crossencoder` / `crossencoder_context` / `clean_chunk`, hyphenation ingest flag, deterministic RRF ties (uncommitted on WT).
- **Draft results** (`evals/results/_draft_ablation.md`, DRAFT — NOT FOR REPORTING, n=20):  
  default **0.425** / 124.8w; term **0.100** / ~30w; crossencoder **0.150** / ~27–47w; **clean_chunk 0.650 / 99.3w**.  
  Diagnose: losses mostly scoring (14), splitting 1, cap 0.

## 5. Evaluation

- Questions: **99** in `evals/data/questions.jsonl` — tune 28 / test 71; **`human_verified`: 0** (all `draft`).
- Baseline for headline reporting: **none** (needs verified labels).
- Results (label status):
  - `20261113_default_test.json`: draft; Recall@4 **0.667**, MRR **0.533**, not_found_acc **0.718**; retrieval latency p50 **27ms** / p95 **41ms** (eval index).
  - `20261113_default_tune.json`: draft (present).
  - `_draft_ablation.md`: DRAFT ablations (see §4).
  - `_ci_synthetic_smoke.md`: DRAFT CI smoke Recall@4 **0.804** (pass).
  - `_default_behaviour_snapshot.json`: regression lock (not a quality baseline).

## 6. Tests

Ran: `pytest tests/ -q` (venv), **2026-11-14**.  
**122 passed**, **0 failed**, **0 skipped**, **90.85s**. Failing tests: **none**.

## 7. UI state

Known / recent (mostly dirty `chat-screen` WT; not on `main`):

- Light/dark: tokenised CSS intended; residual risk of Streamlit BaseWeb defaults flashing — **unverified** live.
- Developer text: mode banner removed from Chat on WT; Settings still explains extractive; Advanced details + ranking % only with `ui_developer_mode` (WT). Sidebar status **dot** + tooltip (WT).  
- `main` UI may still show older Connected/provider chips / banners — **unverified** without checking out `main` UI run.
- Possible scope duplicate caption: intended fixed on WT (single chip) — **unverified** live.

## 8. Library (local `data/chatbot.db`)

Indexed now (**9**):

| File | Flag |
|------|------|
| `Liyakat_Hussain_Resume.pdf` | **Personal resume — remove for demo** |
| `MediAssist_Project_Report_final-version (2).pdf` | Project report — review for demo |
| `deepfake documentation.pdf` | Review for demo |
| `inject_ignore_previous.pdf` | **Test/injection fixture** (added during §9 timing) |
| `perf.pdf`, `qa_design.pdf`, `smoke_ada.pdf`, `smoke_ada2.pdf`, `smoke_ada3.pdf` | **Test/smoke — remove for demo** |

Uploads dir also has multiple other `Liyakat_*Resume*.pdf` copies and smoke PDFs (not all necessarily indexed).

## 9. Performance

| Metric | Result | Notes |
|--------|--------|-------|
| API cold-start to `/health` | **16.7 s** | Temporary uvicorn `:8019` |
| Upload→ready (1-page fixture PDF) | **1.63 s** | Same temp server |
| Chat latency 10 Qs p50 / p95 | **65.5 / 98.0 ms** | Extractive, after upload |
| Eval-index 10 Q extractive p50 / p95 | **74 / 258 ms** | Isolated eval index |
| Streamlit cold-start | **unverified** | |
| Settings/module import | **0.49 s** | Not full app start |

## 10. Deployment

- **Docker:** `Dockerfile` + `docker-compose.yml` present; **`docker` CLI not installed** on this machine → run status **unverified**.
- **Hugging Face Space:** `README_HF.md` documents Docker Space; live Space status **unverified**.
- **Demo mode:** no dedicated `DEMO_MODE` flag found; offline extractive via env is the practical demo path.

## 11. Repo hygiene

- README: present and substantial. Licence file in repo root: **missing** (`LICENSE*` not found; HF readme claims `mit`).
- `.env.example`: present (offline defaults). `.env`: local only (gitignored); contains API key material.
- Committed PDFs: eval corpus + injection fixtures (OK). **Personal resumes in local `uploads/` / DB, not verified as git-tracked.** Fictional resume fixture exists uncommitted under `tests/fixtures/`.
- Large files: under `.venv` / site-packages (not for commit). Leftover: `streamlit_app/styles/_extract_css.py` present; debug leftovers **unverified** beyond that.
- Secrets in git: `.env` ignored; spot-check did not list committed `.env` / real resumes.

## 12. Dependencies

- `requirements.txt`: mostly **lower-bound ranges** (`>=`, `<`), not fully pin-locked (`==` rare).
- Recent install issues: **unverified** this session; pymupdf pin history noted in prior work as flaky — not re-verified now. Venv present; tests ran.

## 13. Top 10 live-demo risks (most serious first)

1. **Personal resume + smoke/injection docs in the live library** — privacy / unprofessional Q&A.
2. **Zero human-verified labels** — cannot defend accuracy numbers; extractive can miss or dump chunks.
3. **Dirty `chat-screen` tree ≠ `main`** — demo may run uncommitted UI/backend; hard to reproduce.
4. **Default config `llm_provider=openai` if `.env` missing** — cloud calls / key errors mid-demo.
5. **Cold start ~17s** — first load looks broken without a warmup script.
6. **Enabling refusal / sentence_term without checking** — uncalibrated refusal or worse key-fact coverage.
7. **Docker/HF unproven on this machine** — cannot fall back to Space if local fails.
8. **Near-duplicate midcap SIDs in eval corpus** — easy wrong-fund answers if those are uploaded.
9. **Cross-encoder / first model download** if reranker or CE sentence mode flipped on.
10. **No root LICENSE** while HF metadata claims MIT — compliance/confusion if asked.
