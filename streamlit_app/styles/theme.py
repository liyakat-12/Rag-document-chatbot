"""DocuMind AI theme — navy / teal enterprise colour system (light + dark).

Design tokens are centralized here. Streamlit's dark-mode toggle in the
sidebar switches between LIGHT_CSS and DARK_CSS via apply_theme().

Light
  Primary navy #172B4D · action teal #0F766E · hover #115E59
  bg #F8FAFC · surface #FFFFFF · text #172B4D · secondary #64748B
  border #E2E8F0 · teal soft #CCFBF1
  success #15803D · warning #B45309 · error #B91C1C

Dark
  bg #0B1220 · sidebar #111827 · surface #172033
  text #F1F5F9 · secondary #CBD5E1 · border #334155
  action #2DD4BF · teal soft #123B3A
  success #4ADE80 · warning #FBBF24 · error #F87171
"""

from __future__ import annotations

_STRUCTURE = """
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&family=Fraunces:opsz,wght@9..144,600;9..144,700&display=swap');

html, body, .stApp, [data-testid="stAppViewContainer"],
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p,
label, .stCaption, [data-testid="stWidgetLabel"] {
  font-family: "DM Sans", "Segoe UI", sans-serif !important;
}

.stApp {
  background: var(--dm-bg) !important;
  color: var(--dm-ink) !important;
}

header[data-testid="stHeader"],
div[data-testid="stToolbar"],
div[data-testid="stDecoration"],
div[data-testid="stStatusWidget"],
#MainMenu,
footer {
  display: none !important;
  visibility: hidden !important;
  height: 0 !important;
}

.block-container,
[data-testid="stMainBlockContainer"],
.stMainBlockContainer {
  padding-top: 1.5rem !important;
  padding-bottom: 3rem !important;
  max-width: 880px !important;
}

section.main { padding-top: 0.25rem !important; }

/* —— Sidebar —— */
[data-testid="stSidebar"] {
  background: var(--dm-sidebar) !important;
  border-right: 1px solid var(--dm-line) !important;
}
[data-testid="stSidebar"] > div:first-child {
  padding-top: 1.25rem !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span {
  color: var(--dm-ink) !important;
}
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
  color: var(--dm-secondary) !important;
  letter-spacing: normal !important;
  font-variant-numeric: tabular-nums;
}
[data-testid="stSidebar"] [data-testid="stExpander"] {
  border: 1px solid var(--dm-line) !important;
  background: var(--dm-surface) !important;
  margin-top: 0.65rem !important;
}
[data-testid="stSidebar"] .stButton > button {
  overflow: hidden !important;
  text-overflow: ellipsis !important;
  white-space: nowrap !important;
  font-size: 0.84rem !important;
}
[data-testid="stSidebar"] [role="radiogroup"] label {
  border-radius: 10px !important;
  padding: 0.45rem 0.65rem !important;
  margin-bottom: 0.2rem !important;
  border: 1px solid transparent !important;
  transition: background .15s ease, border-color .15s ease;
}
[data-testid="stSidebar"] [role="radiogroup"] label:hover {
  background: var(--dm-surface-2) !important;
}
[data-testid="stSidebar"] [role="radiogroup"] label[data-checked="true"],
[data-testid="stSidebar"] [role="radiogroup"] label:has(input:checked) {
  background: var(--dm-accent-soft) !important;
  border-color: var(--dm-accent) !important;
  color: var(--dm-accent) !important;
}

/* Page select — selected value uses brand tint */
[data-testid="stSidebar"] [data-baseweb="select"] > div {
  background: var(--dm-surface) !important;
  border-color: var(--dm-line) !important;
  color: var(--dm-ink) !important;
}

h1,h2,h3,.stMarkdown h1,.stMarkdown h2,.stMarkdown h3 {
  font-family: "Fraunces", Georgia, serif !important;
  color: var(--dm-ink) !important;
  letter-spacing: -0.03em;
  font-weight: 700 !important;
}

[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li,
.stMarkdown, label {
  color: var(--dm-ink) !important;
  line-height: 1.55;
}
.stCaption,
[data-testid="stCaptionContainer"],
[data-testid="stCaptionContainer"] p {
  color: var(--dm-secondary) !important;
}
a { color: var(--dm-accent) !important; }

/* —— Controls —— */
.stButton > button,
[data-testid="stDownloadButton"] button,
.stDownloadButton > button {
  border-radius: 10px !important;
  border: 1px solid var(--dm-line) !important;
  background: var(--dm-surface) !important;
  color: var(--dm-ink) !important;
  font-weight: 600 !important;
  font-family: "DM Sans", sans-serif !important;
  box-shadow: none !important;
  transition: border-color .15s ease, background .15s ease, color .15s ease;
}
.stButton > button:hover,
[data-testid="stDownloadButton"] button:hover,
.stDownloadButton > button:hover {
  border-color: var(--dm-accent) !important;
  color: var(--dm-accent) !important;
  background: var(--dm-accent-soft) !important;
}
.stButton > button:focus-visible,
[data-testid="stDownloadButton"] button:focus-visible,
.stDownloadButton > button:focus-visible,
.stTextInput input:focus-visible,
.stMultiSelect [data-baseweb="select"]:focus-within,
[data-testid="stChatInput"]:focus-within,
[data-baseweb="select"]:focus-within {
  outline: 2px solid var(--dm-accent) !important;
  outline-offset: 2px !important;
}
.stButton > button:disabled,
.stButton > button[disabled],
[data-testid="stDownloadButton"] button:disabled {
  opacity: 0.55 !important;
  color: var(--dm-secondary) !important;
  border-color: var(--dm-line) !important;
  background: var(--dm-surface-2) !important;
  cursor: not-allowed !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
  background: var(--dm-accent) !important;
  color: var(--dm-on-accent) !important;
  border: 1px solid var(--dm-accent) !important;
  box-shadow: none !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--dm-accent-hover) !important;
  border-color: var(--dm-accent-hover) !important;
  color: var(--dm-on-accent) !important;
}
.stButton > button[kind="primary"]:disabled {
  background: var(--dm-surface-2) !important;
  color: var(--dm-muted) !important;
  border-color: var(--dm-line) !important;
}

[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"],
.stApp [data-testid="stBottom"] {
  background: var(--dm-bg) !important;
}

[data-testid="stFileUploaderDropzone"] {
  background: var(--dm-surface) !important;
  border: 1.5px dashed var(--dm-line-strong) !important;
  border-radius: 12px !important;
  padding: 1.25rem !important;
  color: var(--dm-secondary) !important;
}
[data-testid="stFileUploaderDropzone"]:hover {
  border-color: var(--dm-accent) !important;
  background: var(--dm-accent-soft) !important;
}
[data-testid="stFileUploaderDropzone"] small,
[data-testid="stFileUploaderDropzone"] span {
  color: var(--dm-secondary) !important;
}

[data-testid="stChatInput"] {
  background: var(--dm-surface) !important;
  border: 1px solid var(--dm-line) !important;
  border-radius: 14px !important;
  box-shadow: var(--dm-shadow) !important;
}
[data-testid="stChatInput"] textarea,
[data-testid="stChatInput"] input {
  color: var(--dm-ink) !important;
  caret-color: var(--dm-accent) !important;
}
/* Send arrow — always navy brand, not a washed-out disabled chip */
[data-testid="stChatInputSubmitButton"],
[data-testid="stChatInput"] button[data-testid="stChatInputSubmitButton"],
[data-testid="stChatInput"] button {
  background: var(--dm-accent) !important;
  background-color: var(--dm-accent) !important;
  color: var(--dm-on-accent) !important;
  border: none !important;
  border-radius: 10px !important;
  opacity: 1 !important;
}
[data-testid="stChatInputSubmitButton"] svg,
[data-testid="stChatInput"] button svg {
  fill: var(--dm-on-accent) !important;
  color: var(--dm-on-accent) !important;
}
[data-testid="stChatInputSubmitButton"]:hover:not(:disabled),
[data-testid="stChatInput"] button:hover:not(:disabled) {
  background: var(--dm-accent-hover) !important;
  background-color: var(--dm-accent-hover) !important;
}
[data-testid="stChatInputSubmitButton"]:disabled,
[data-testid="stChatInput"] button:disabled {
  background: var(--dm-accent) !important;
  background-color: var(--dm-accent) !important;
  color: var(--dm-on-accent) !important;
  opacity: 0.72 !important;
}

.stTextInput input,
.stTextArea textarea,
.stNumberInput input,
.stMultiSelect [data-baseweb="select"] > div,
.stSelectbox [data-baseweb="select"] > div {
  background: var(--dm-surface) !important;
  color: var(--dm-ink) !important;
  border-color: var(--dm-line) !important;
  border-radius: 10px !important;
}

/* Multiselect tags — brand tint, readable */
.stMultiSelect [data-baseweb="tag"] {
  background: var(--dm-accent-soft) !important;
  color: var(--dm-accent) !important;
  border-radius: 6px !important;
}
.stMultiSelect [data-baseweb="tag"] span {
  color: var(--dm-accent) !important;
}

/* Toggle */
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p,
[data-testid="stSidebar"] label[data-baseweb="checkbox"] {
  color: var(--dm-ink) !important;
}
[data-baseweb="checkbox"] input:checked + div,
[role="switch"][aria-checked="true"] {
  background-color: var(--dm-accent) !important;
}

/* —— Chat messages —— */
div[data-testid="stChatMessage"] {
  background: var(--dm-surface) !important;
  border: 1px solid var(--dm-line) !important;
  border-radius: 14px !important;
  box-shadow: var(--dm-shadow);
  padding: 0.55rem 0.75rem !important;
  margin-bottom: 0.85rem !important;
}
div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
  background: var(--dm-user) !important;
  border-color: var(--dm-line) !important;
}

[data-testid="stMetric"] {
  background: var(--dm-surface);
  border: 1px solid var(--dm-line);
  border-radius: 14px;
  padding: 0.85rem 1rem;
  box-shadow: var(--dm-shadow);
}
[data-testid="stMetricLabel"],
[data-testid="stMetricDelta"] {
  color: var(--dm-secondary) !important;
}
[data-testid="stMetricValue"] {
  color: var(--dm-ink) !important;
}

[data-testid="stExpander"] {
  background: var(--dm-surface) !important;
  border: 1px solid var(--dm-line) !important;
  border-radius: 12px !important;
}
[data-testid="stExpander"] summary,
[data-testid="stExpander"] details summary {
  color: var(--dm-ink) !important;
}

/* Alerts — status colours with readable text */
[data-testid="stAlert"] {
  border-radius: 12px !important;
  border: 1px solid var(--dm-line) !important;
}
[data-testid="stAlert"] [data-testid="stMarkdownContainer"] p {
  color: var(--dm-ink) !important;
}

div[data-testid="stCode"],
.stCodeBlock {
  background: var(--dm-surface-2) !important;
  border: 1px solid var(--dm-line) !important;
  border-radius: 10px !important;
  color: var(--dm-ink) !important;
}

hr, [data-testid="stDivider"] {
  border-color: var(--dm-line) !important;
  background: var(--dm-line) !important;
}

/* —— Brand & layout atoms —— */
.brand-mark {
  display: flex;
  align-items: center;
  gap: 0.65rem;
  margin-bottom: 0.35rem;
}
.brand-mark .logo {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  background: #172B4D;
  color: #FFFFFF;
  font-family: "Fraunces", Georgia, serif;
  font-weight: 700;
  font-size: 1.05rem;
  display: flex;
  align-items: center;
  justify-content: center;
  letter-spacing: -0.04em;
  flex-shrink: 0;
}
.brand-title {
  font-family: "Fraunces", Georgia, serif;
  font-weight: 700;
  font-size: 1.4rem;
  color: var(--dm-ink) !important;
  margin: 0;
  letter-spacing: -0.03em;
  line-height: 1.15;
}
.brand-tag {
  color: var(--dm-secondary) !important;
  font-size: 0.8rem;
  margin: 0.15rem 0 0.9rem;
  line-height: 1.4;
}
.brand-hero {
  font-family: "DM Sans", sans-serif;
  font-weight: 600;
  font-size: 0.72rem;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--dm-accent) !important;
  text-align: center;
  margin: 0.5rem 0 0.35rem;
}
.nav-hint {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--dm-muted) !important;
  margin: 1rem 0 0.45rem;
}
.hero-wrap {
  text-align: center;
  padding: 1.75rem 1rem 1.25rem;
  margin: 0.25rem 0 1.25rem;
  border-radius: 16px;
  background: var(--dm-surface);
  border: 1px solid var(--dm-line);
  box-shadow: var(--dm-shadow);
}
.hero-title {
  font-family: "Fraunces", Georgia, serif;
  font-size: clamp(1.85rem, 4vw, 2.45rem);
  font-weight: 700;
  letter-spacing: -0.035em;
  color: var(--dm-ink) !important;
  margin: 0.35rem 0 0.55rem;
  line-height: 1.15;
}
.hero-sub {
  color: var(--dm-secondary) !important;
  margin: 0 auto;
  max-width: 28rem;
  font-size: 1.02rem;
  line-height: 1.5;
}
.suggest-card {
  border: 1px solid var(--dm-line);
  background: var(--dm-surface);
  border-radius: 12px;
  padding: 0.95rem 1.05rem;
  min-height: 3.6rem;
  color: var(--dm-ink);
  font-size: 0.92rem;
  line-height: 1.45;
  box-shadow: var(--dm-shadow);
}
.suggest-card:hover {
  border-color: var(--dm-accent);
}
.doc-card {
  border: 1px solid var(--dm-line);
  background: var(--dm-surface);
  border-radius: 14px;
  padding: 1.05rem 1.15rem;
  margin-bottom: 0.35rem;
  box-shadow: var(--dm-shadow);
}
.doc-card-title {
  font-size: 1.02rem;
  font-weight: 650;
  margin-bottom: 0.35rem;
  color: var(--dm-ink);
  overflow-wrap: anywhere;
  word-break: break-word;
  line-height: 1.35;
}
.doc-card-meta {
  color: var(--dm-secondary);
  font-size: 0.9rem;
  margin-bottom: 0.35rem;
}
.meta-chip {
  display: inline-block;
  padding: 0.2rem 0.55rem;
  border-radius: 8px;
  background: var(--dm-accent-soft);
  color: var(--dm-accent) !important;
  font-weight: 650;
  font-size: 0.7rem;
  margin-right: 0.3rem;
  margin-bottom: 0.25rem;
  letter-spacing: 0.02em;
}
.conf-bar {
  height: 5px;
  border-radius: 999px;
  background: var(--dm-surface-2);
  overflow: hidden;
  margin: 0.4rem 0 0.2rem;
  max-width: 200px;
}
.conf-bar > span {
  display: block;
  height: 100%;
  background: var(--dm-accent);
  border-radius: 999px;
}
.mode-banner {
  border: 1px solid var(--dm-line);
  background: var(--dm-accent-soft);
  color: var(--dm-ink) !important;
  border-radius: 12px;
  padding: 0.65rem 0.9rem;
  font-size: 0.84rem;
  margin: 0.75rem 0 1rem;
  line-height: 1.45;
}
.mode-banner, .mode-banner * { color: var(--dm-ink) !important; }
.mode-banner code {
  background: var(--dm-surface) !important;
  color: var(--dm-accent) !important;
  padding: 0.08rem 0.35rem;
  border-radius: 5px;
  font-size: 0.8em;
  border: 1px solid var(--dm-line);
}
.status-ok { color: var(--dm-ok) !important; font-weight: 650; }
.status-warn { color: var(--dm-warn) !important; font-weight: 650; }
.status-err { color: var(--dm-danger) !important; font-weight: 650; }
.status-info { color: var(--dm-info) !important; font-weight: 650; }
.stage-ok { color: var(--dm-ok) !important; }
.stage-line { font-size: 0.9rem; margin: 0.2rem 0; color: var(--dm-ink) !important; }
.page-kicker {
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--dm-accent) !important;
  margin: 0 0 0.35rem;
}
.divider-soft {
  height: 1px;
  background: var(--dm-line);
  margin: 0.85rem 0 0.65rem;
  border: none;
}

/* Empty / info states */
[data-testid="stAlert"][kind="info"],
div[data-baseweb="notification"] {
  border-left: 3px solid var(--dm-info);
}

/* Health / status chips */
.health-ok { color: var(--dm-ok) !important; font-weight: 650; }
.health-warn { color: var(--dm-warn) !important; font-weight: 650; }
.health-err { color: var(--dm-danger) !important; font-weight: 650; }

/* Evidence labels */
.evidence-strong { color: var(--dm-ok) !important; }
.evidence-limited { color: var(--dm-warn) !important; }
.evidence-none { color: var(--dm-danger) !important; }

/* Scope chip row */
.scope-hint {
  font-size: 0.82rem;
  color: var(--dm-secondary) !important;
  margin: 0.15rem 0 0.65rem;
}

/* Architecture diagram box */
.arch-box {
  background: var(--dm-surface);
  border: 1px solid var(--dm-line);
  border-radius: 12px;
  padding: 1rem 1.15rem;
  margin: 0.75rem 0 1rem;
  font-family: "DM Sans", sans-serif;
  font-size: 0.88rem;
  line-height: 1.65;
  color: var(--dm-ink);
  overflow-x: auto;
}
.arch-box code {
  background: var(--dm-accent-soft) !important;
  color: var(--dm-accent) !important;
  border: none !important;
}

/* Prevent long filenames from blowing out layout */
[data-testid="stChatMessage"],
.doc-card-title,
[data-testid="stSidebar"] .stButton > button {
  overflow-wrap: anywhere;
  word-break: break-word;
}

@media (max-width: 768px) {
  .block-container,
  [data-testid="stMainBlockContainer"],
  .stMainBlockContainer {
    max-width: 100% !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
  }
}
"""

LIGHT_CSS = f"""
<style>
{_STRUCTURE}
:root {{
  --dm-bg: #F8FAFC;
  --dm-bg-top: #F8FAFC;
  --dm-glow: transparent;
  --dm-glow-2: transparent;
  --dm-sidebar: #FFFFFF;
  --dm-surface: #FFFFFF;
  --dm-surface-2: #F1F5F9;
  --dm-hero-bg: #FFFFFF;
  --dm-ink: #172B4D;
  --dm-ink-soft: #172B4D;
  --dm-secondary: #64748B;
  --dm-muted: #94A3B8;
  --dm-line: #E2E8F0;
  --dm-line-strong: #CBD5E1;
  --dm-line-accent: #99A8C0;
  --dm-navy: #172B4D;
  --dm-accent: #0F766E;
  --dm-accent-deep: #115E59;
  --dm-accent-soft: #CCFBF1;
  --dm-accent-hover: #115E59;
  --dm-on-accent: #FFFFFF;
  --dm-danger: #B91C1C;
  --dm-warn: #B45309;
  --dm-ok: #15803D;
  --dm-info: #0F766E;
  --dm-user: #F1F5F9;
  --dm-shadow: 0 1px 2px rgba(23, 43, 77, 0.04), 0 1px 3px rgba(23, 43, 77, 0.06);
  --dm-shadow-lg: 0 4px 12px rgba(23, 43, 77, 0.08);
}}
</style>
"""

DARK_CSS = f"""
<style>
{_STRUCTURE}
:root {{
  --dm-bg: #0B1220;
  --dm-bg-top: #0B1220;
  --dm-glow: transparent;
  --dm-glow-2: transparent;
  --dm-sidebar: #111827;
  --dm-surface: #172033;
  --dm-surface-2: #1E293B;
  --dm-hero-bg: #172033;
  --dm-ink: #F1F5F9;
  --dm-ink-soft: #F1F5F9;
  --dm-secondary: #CBD5E1;
  --dm-muted: #94A3B8;
  --dm-line: #334155;
  --dm-line-strong: #475569;
  --dm-line-accent: #64748B;
  --dm-navy: #172B4D;
  --dm-accent: #2DD4BF;
  --dm-accent-deep: #14B8A6;
  --dm-accent-soft: #123B3A;
  --dm-accent-hover: #5EEAD4;
  --dm-on-accent: #0B1220;
  --dm-danger: #F87171;
  --dm-warn: #FBBF24;
  --dm-ok: #4ADE80;
  --dm-info: #2DD4BF;
  --dm-user: #1E293B;
  --dm-shadow: 0 1px 2px rgba(0, 0, 0, 0.35);
  --dm-shadow-lg: 0 4px 16px rgba(0, 0, 0, 0.4);
}}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span,
[data-testid="stChatMessage"] *,
[data-testid="stMetricValue"],
[data-testid="stMetricLabel"] {{
  color: var(--dm-ink) !important;
}}
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
.stCaption,
[data-testid="stCaptionContainer"] p {{
  color: var(--dm-secondary) !important;
}}
a {{ color: var(--dm-accent) !important; }}

/* Force BaseWeb selects / chat composer onto dark surfaces */
.stMultiSelect [data-baseweb="select"] > div,
.stSelectbox [data-baseweb="select"] > div,
[data-baseweb="select"] > div,
.stTextInput input,
.stTextArea textarea {{
  background-color: var(--dm-surface) !important;
  color: var(--dm-ink) !important;
  border-color: var(--dm-line) !important;
}}
[data-baseweb="popover"] [data-baseweb="menu"],
[data-baseweb="popover"] ul,
[data-baseweb="menu"] {{
  background-color: var(--dm-surface) !important;
  color: var(--dm-ink) !important;
  border: 1px solid var(--dm-line) !important;
}}
[data-baseweb="menu"] li,
[data-baseweb="option"] {{
  color: var(--dm-ink) !important;
}}
[data-baseweb="menu"] li:hover,
[data-baseweb="option"]:hover,
[aria-selected="true"] {{
  background-color: var(--dm-accent-soft) !important;
  color: var(--dm-accent) !important;
}}
[data-testid="stChatInput"],
[data-testid="stChatInput"] > div {{
  background-color: var(--dm-surface) !important;
  border-color: var(--dm-line) !important;
}}
[data-testid="stChatInput"] textarea {{
  background-color: transparent !important;
  color: var(--dm-ink) !important;
}}
[data-testid="stChatInput"] textarea::placeholder {{
  color: var(--dm-muted) !important;
}}
[data-testid="stChatInputSubmitButton"],
[data-testid="stChatInput"] button {{
  background: var(--dm-accent) !important;
  background-color: var(--dm-accent) !important;
  color: var(--dm-on-accent) !important;
}}
[data-testid="stChatInputSubmitButton"] svg {{
  fill: var(--dm-on-accent) !important;
  color: var(--dm-on-accent) !important;
}}
</style>
"""


def apply_theme(dark: bool) -> str:
    """Return injected <style> for the active appearance (wired to sidebar toggle)."""
    return DARK_CSS if dark else LIGHT_CSS
