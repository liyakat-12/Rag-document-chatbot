# Chat screen redesign (≤10 lines)

1. **Branch:** `chat-screen` from `answer-quality`. UI-only (`streamlit_app/` + `styles/theme.py`).
2. **Layout:** centred max-width **760px**; bottom padding ~7.5rem; composer same width; header hidden.
3. **Dev chrome:** Offline status **dot** (tooltip); Connected/extractive pills + mode banner → Settings.
4. **Contrast:** navy primary buttons; secondary text `#475569`; user bubble light teal `#CCFBF1`.
5. **Messages:** right-aligned user bubble (no avatar); assistant card = badge → answer → sources → hover actions.
6. **Scope:** chip “All documents (N) ▾” / “Searching: …” + popover; no Search-in box.
7. **Sidebar:** Chat/Library/About nav; library rows + status dots; recent row-click; no Clear conversation.
8. **Check:** (1) empty chat light 1280 (2) thread + sources dark 1280 (3) scoped chip + input 1920 (4) Library/About nav.
