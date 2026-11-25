# Release-1 report

## Stage 1 — Branch consolidation

**Done.** Branch `release-1` created from `main` (`a1f86fd`), then fast-forward merged:

| Branch | Contained in `release-1`? |
|--------|---------------------------|
| `phase-1-eval-foundation` | yes |
| `unattended-1` / `phase-2-baseline-refusal` | yes (same tip) |
| `unattended-2` | yes |
| `unattended-3` / `answer-quality` tip | yes |
| `chat-screen` (incl. WIP commit `1ece8ad`) | yes |
| `unattended-3-docx-wip` | **no** — DOCX ingest is not behind a feature flag (`.docx` enabled by default on that WIP); left out per brief |

Tests after each merge: phase-1 **49**, unattended-1 **70**, unattended-2 **92**, unattended-3 **110**, chat-screen **122** — all passed.

No branches deleted.

## Stage 2 — Safe defaults and reliability

**Done.** Defaults: `llm_provider=extractive`, `embedding_provider=local`. Config validation with friendly errors. Async warmup; `/health` status `starting`→`ok`/`degraded` + `ready`. Requirements pinned (`==`) + `requirements-optional.txt`. Deterministic RRF retained. Tests: **125 passed**.

## Remaining stages

3–9 pending (answer quality defaults, demo mode, UI, evals, repo, deploy, docs).
