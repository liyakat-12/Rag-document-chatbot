"""One-shot helper to build styles.css from theme.py structure."""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent
text = (ROOT / "theme.py").read_text(encoding="utf-8")
m = re.search(r'_STRUCTURE = """(.*?)"""', text, re.S)
if not m:
    raise SystemExit("no _STRUCTURE")
s = m.group(1)
s = s.replace("color: #FFFFFF !important;", "color: var(--dm-accent-text) !important;")
s = s.replace("background: #172B4D;", "background: var(--dm-navy);")
s = s.replace("color: #FFFFFF;", "color: var(--dm-accent-text);")
# Comments that mention hex are fine in tokens only — strip hex from comments in structure
s = re.sub(r"/\*[^*]*#[0-9A-Fa-f]{3,8}[^*]*\*/", "/* contrast note */", s)

LIGHT = """
:root {
  --dm-background: #F8FAFC;
  --dm-surface: #FFFFFF;
  --dm-surface-raised: #F1F5F9;
  --dm-border: #CBD5E1;
  --dm-text: #172B4D;
  --dm-text-muted: #475569;
  --dm-accent: #0F766E;
  --dm-accent-text: #FFFFFF;
  --dm-danger: #B91C1C;
  --dm-warning: #B45309;
  /* aliases / extras */
  --dm-bg: var(--dm-background);
  --dm-bg-top: var(--dm-background);
  --dm-glow: transparent;
  --dm-glow-2: transparent;
  --dm-sidebar: #FFFFFF;
  --dm-surface-2: var(--dm-surface-raised);
  --dm-hero-bg: var(--dm-surface);
  --dm-ink: var(--dm-text);
  --dm-ink-soft: var(--dm-text);
  --dm-secondary: var(--dm-text-muted);
  --dm-muted: #64748B;
  --dm-line: var(--dm-border);
  --dm-line-strong: #94A3B8;
  --dm-line-accent: #99A8C0;
  --dm-navy: #172B4D;
  --dm-accent-deep: #115E59;
  --dm-accent-soft: #CCFBF1;
  --dm-accent-hover: #115E59;
  --dm-on-accent: var(--dm-accent-text);
  --dm-warn: var(--dm-warning);
  --dm-ok: #15803D;
  --dm-info: var(--dm-accent);
  --dm-user: #CCFBF1;
  --dm-shadow: 0 1px 2px rgba(23, 43, 77, 0.04), 0 1px 3px rgba(23, 43, 77, 0.06);
  --dm-shadow-lg: 0 4px 12px rgba(23, 43, 77, 0.08);
}
"""

DARK = """
:root {
  --dm-background: #0B1220;
  --dm-surface: #172033;
  --dm-surface-raised: #1E293B;
  --dm-border: #64748B;
  --dm-text: #F1F5F9;
  --dm-text-muted: #CBD5E1;
  --dm-accent: #2DD4BF;
  --dm-accent-text: #0B1220;
  --dm-danger: #F87171;
  --dm-warning: #FBBF24;
  /* aliases / extras */
  --dm-bg: var(--dm-background);
  --dm-bg-top: var(--dm-background);
  --dm-glow: transparent;
  --dm-glow-2: transparent;
  --dm-sidebar: #111827;
  --dm-surface-2: var(--dm-surface-raised);
  --dm-hero-bg: var(--dm-surface);
  --dm-ink: var(--dm-text);
  --dm-ink-soft: var(--dm-text);
  --dm-secondary: var(--dm-text-muted);
  --dm-muted: #94A3B8;
  --dm-line: var(--dm-border);
  --dm-line-strong: #94A3B8;
  --dm-line-accent: #94A3B8;
  --dm-navy: #172B4D;
  --dm-accent-deep: #14B8A6;
  --dm-accent-soft: #123B3A;
  --dm-accent-hover: #5EEAD4;
  --dm-on-accent: var(--dm-accent-text);
  --dm-warn: var(--dm-warning);
  --dm-ok: #4ADE80;
  --dm-info: var(--dm-accent);
  --dm-user: #123B3A;
  --dm-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
  --dm-shadow-lg: 0 4px 16px rgba(0, 0, 0, 0.4);
}
"""

EXTRA_WIDGETS = """
/* —— Explicit Streamlit widgets (data-testid) —— */
[data-testid="stSidebar"] .stButton > button,
[data-testid="stSidebar"] [data-testid="stDownloadButton"] button {
  background: var(--dm-surface) !important;
  color: var(--dm-text) !important;
  border: 1px solid var(--dm-border) !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: var(--dm-accent-soft) !important;
  color: var(--dm-accent) !important;
  border-color: var(--dm-accent) !important;
}
[data-testid="baseButton-secondary"],
.stButton > button[kind="secondary"] {
  background: var(--dm-surface) !important;
  color: var(--dm-text) !important;
  border: 1px solid var(--dm-border) !important;
}
[data-testid="stExpander"] details,
[data-testid="stExpander"] {
  background: var(--dm-surface) !important;
  border: 1px solid var(--dm-border) !important;
  color: var(--dm-text) !important;
}
[data-testid="stExpander"] summary {
  color: var(--dm-text) !important;
}
.sess-row .stButton > button,
[data-testid="stSidebar"] .sess-row .stButton > button {
  background: var(--dm-surface-raised) !important;
  color: var(--dm-text) !important;
  border: 1px solid var(--dm-border) !important;
  text-align: left !important;
  justify-content: flex-start !important;
}
.brand-mark .logo {
  background: var(--dm-navy) !important;
  color: var(--dm-accent-text) !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
  background: var(--dm-navy) !important;
  color: var(--dm-accent-text) !important;
  border: 1px solid var(--dm-navy) !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--dm-accent-deep) !important;
  border-color: var(--dm-accent-deep) !important;
  color: var(--dm-accent-text) !important;
}
"""

DARK_OVERRIDES = """
/* Dark-mode primary uses accent with accent-text (set via tokens) */
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
  background: var(--dm-accent-deep) !important;
  color: var(--dm-accent-text) !important;
  border-color: var(--dm-accent-deep) !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--dm-accent) !important;
  border-color: var(--dm-accent) !important;
  color: var(--dm-accent-text) !important;
}
.nav-link-btn.active .stButton > button,
.nav-link-btn .stButton > button:hover {
  color: var(--dm-accent) !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span,
[data-testid="stChatMessage"] *,
[data-testid="stMetricValue"],
[data-testid="stMetricLabel"] {
  color: var(--dm-text) !important;
}
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
.stCaption,
[data-testid="stCaptionContainer"] p {
  color: var(--dm-text-muted) !important;
}
a { color: var(--dm-accent) !important; }
.stMultiSelect [data-baseweb="select"] > div,
.stSelectbox [data-baseweb="select"] > div,
[data-baseweb="select"] > div,
.stTextInput input,
.stTextArea textarea {
  background-color: var(--dm-surface) !important;
  color: var(--dm-text) !important;
  border-color: var(--dm-border) !important;
}
[data-baseweb="popover"] [data-baseweb="menu"],
[data-baseweb="popover"] ul,
[data-baseweb="menu"] {
  background-color: var(--dm-surface) !important;
  color: var(--dm-text) !important;
  border: 1px solid var(--dm-border) !important;
}
[data-baseweb="menu"] li,
[data-baseweb="option"] {
  color: var(--dm-text) !important;
}
[data-baseweb="menu"] li:hover,
[data-baseweb="option"]:hover,
[aria-selected="true"] {
  background-color: var(--dm-accent-soft) !important;
  color: var(--dm-accent) !important;
}
[data-testid="stChatInput"],
[data-testid="stChatInput"] > div {
  background-color: var(--dm-surface) !important;
  border-color: var(--dm-border) !important;
}
[data-testid="stChatInput"] textarea {
  background-color: transparent !important;
  color: var(--dm-text) !important;
}
[data-testid="stChatInput"] textarea::placeholder {
  color: var(--dm-muted) !important;
}
[data-testid="stChatInputSubmitButton"],
[data-testid="stChatInput"] button {
  background: var(--dm-accent) !important;
  background-color: var(--dm-accent) !important;
  color: var(--dm-accent-text) !important;
}
[data-testid="stChatInputSubmitButton"] svg {
  fill: var(--dm-accent-text) !important;
  color: var(--dm-accent-text) !important;
}
"""

out = []
out.append("/* DocuMind theme — colours only inside @@tokens blocks */\n")
out.append("/* @@tokens:light */")
out.append(LIGHT.strip())
out.append("/* @@/tokens:light */\n")
out.append("/* @@tokens:dark */")
out.append(DARK.strip())
out.append("/* @@/tokens:dark */\n")
out.append("/* @@structure */")
out.append(s.strip())
out.append(EXTRA_WIDGETS.strip())
out.append("/* @@/structure */\n")
out.append("/* @@dark-overrides */")
out.append(DARK_OVERRIDES.strip())
out.append("/* @@/dark-overrides */\n")

(ROOT / "styles.css").write_text("\n".join(out) + "\n", encoding="utf-8")
print("wrote", ROOT / "styles.css")
# verify structure has no raw hex
struct = re.search(r"/\\* @@structure \\*/(.*)/\\* @@/structure \\*/", "\n".join(out), re.S)
# simpler check after write
body = (ROOT / "styles.css").read_text(encoding="utf-8")
# strip token blocks for check
stripped = re.sub(
    r"/\* @@tokens:(?:light|dark) \*/.*?/\* @@/tokens:(?:light|dark) \*/",
    "",
    body,
    flags=re.S,
)
hexes = re.findall(r"#[0-9A-Fa-f]{3,8}", stripped)
rgbs = re.findall(r"rgba?\([^)]+\)", stripped)
print("outside tokens hex", hexes)
print("outside tokens rgb", rgbs)
