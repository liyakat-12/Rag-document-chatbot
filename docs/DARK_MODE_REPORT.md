# Dark mode / CSS tokens (≤10 lines)

1. **`streamlit_app/styles/styles.css`:** light+dark `@@tokens` for background, surface, surface-raised, border, text, text-muted, accent, accent-text, danger, warning (+ aliases); structure uses **only** `var(--dm-*)`.
2. **`theme.py`:** loads CSS; toggle swaps token set + dark widget overrides.
3. **Test:** `tests/unit/test_styles_css_tokens.py` fails on hex/rgb/named colours outside tokens — **4 passed**.
4. **Widgets:** buttons, select/multiselect, inputs, chat input, expanders, sidebar, recent rows, Manage documents via `data-testid` + vars; dark **border `#64748B`** (visible on `#0B1220`).
5. **Scope:** single popover chip only (no “Scoped to N of M” caption).
6. **Starters:** heading-derived from selected PDF TOC/lines (replaces summarize / missing-info).
7. **Contrast AA:** audited body pairs — **no failures** (light muted `#64748B` on bg ≈4.55; dark muted ≈7.3).
8. **Check:** toggle Dark mode → Chat (empty + thread), Library recent rows, scope chip, Settings; light then dark.
