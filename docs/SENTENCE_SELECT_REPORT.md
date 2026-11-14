# Sentence-select report (≤10 lines)

1. **Status:** done on `unattended-3` (`0ef54ea`); flags default **off**.
2. **Flags:** `ANSWER_SENTENCE_SELECT`, `INGEST_FIX_HYPHENATION` (env / Settings).
3. **Tests:** `test_sentence_select` + extractive/utils + snapshot → **18 passed**.
4. **Behaviour:** split on `.?!` / bullets / `|`; drop contact lines unless asked; score term(+embed); top 2–3 in doc order; ≤~60 words; per-sentence cites + highlighted context source.
5. **Ablation (DRAFT LABELS — NOT FOR REPORTING):** n=20 draft test w/ key_facts — `extractive_default` key_fact_coverage≈**0.425**, avg_words≈**124.8**; `extractive_sentence_select` ≈**0.100** / **29.9** words.
6. **Files:** `sentence_select.py`, `qa_chain.py`, `text.py`, `ingest.py`, `config.py`, `ablation_runner.py`, `sources.py`, tests.
7. **Unverified:** live UI highlight look; embed blend quality vs term-only.
8. **Remaining:** tune scoring after human-verified labels; DOCX WIP still uncommitted on branch.
