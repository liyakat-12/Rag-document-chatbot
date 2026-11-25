# Answer quality report (≤15 lines) — DRAFT labels

1. **Branch:** `answer-quality` from `unattended-3`; DOCX WIP parked on `unattended-3-docx-wip`.
2. **RRF:** deterministic ties (fused → FAISS → chunk_id); snapshot **3/3 pass**; no re-record.
3. **Diagnose (n=20 draft key_facts):** in_default=9, in_chunks=17, in_selected=2; losses **b_scoring=14**, **a_splitting=1**, **c_cap=0**.
4. **Splitter:** decimals/%/B.Tech/Rs./e.g./No./codes/`R²=0.69` protected; unit tests added.
5. **Variants DRAFT (n=20):** default **0.425**/124.8w; term60/100 **0.100**/30w; CE60/100 **0.150**/27w; CE+ctx60 **0.150**/40w; CE+ctx100 **0.150**/47w; **clean_chunk 0.650/99.3w**.
6. **Candidate default:** only `clean_chunk` beats default coverage with fewer words — **recommend clean_chunk**; default unchanged.
7. **Resume fixture DRAFT:** CE variants 0.875/18w; clean_chunk 0.688/103w; default 0.750/128w (see `_resume_fixture_variants.json`).
8. **UI:** one answer; sources collapsed+highlight; “Found in N documents”; scores in Advanced + `UI_DEVELOPER_MODE`.
9. **Try locally:** `ANSWER_SENTENCE_SELECT=true`, `ANSWER_SENTENCE_SELECT_MODE=clean_chunk`, `LLM_PROVIDER=extractive`.
10. **Flags stay off by default;** snapshot locked.
