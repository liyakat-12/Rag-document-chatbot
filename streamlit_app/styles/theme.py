"""DocuMind AI theme CSS — light and dark enterprise styles."""

from __future__ import annotations

LIGHT_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap');

:root {
  --dm-bg: #f6f7f9;
  --dm-surface: #ffffff;
  --dm-surface-2: #eef1f4;
  --dm-ink: #1a2332;
  --dm-ink-soft: #3d4a5c;
  --dm-muted: #6b7785;
  --dm-line: #e2e6eb;
  --dm-accent: #1f6b5c;
  --dm-accent-soft: #e6f2ef;
  --dm-accent-hover: #185649;
  --dm-danger: #b42318;
  --dm-warn: #b54708;
  --dm-ok: #067647;
  --dm-user: #edf2f7;
  --dm-radius: 12px;
  --dm-shadow: 0 1px 2px rgba(16,24,40,.04), 0 1px 3px rgba(16,24,40,.08);
}

html, body, .stApp, [data-testid="stAppViewContainer"],
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p,
label, .stCaption {
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif !important;
}

.stApp {
  background: var(--dm-bg) !important;
  color: var(--dm-ink) !important;
}

/* Hide Streamlit chrome that overlaps page content (Deploy / menu bar) */
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
  padding-top: 1.75rem !important;
  padding-bottom: 2.5rem !important;
  max-width: 1120px !important;
}

section.main {
  padding-top: 0.5rem !important;
}

[data-testid="stSidebar"] {
  background: var(--dm-surface) !important;
  border-right: 1px solid var(--dm-line) !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span {
  color: var(--dm-ink) !important;
}
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
  color: var(--dm-muted) !important;
}

h1,h2,h3,.stMarkdown h1,.stMarkdown h2,.stMarkdown h3 {
  font-family: "Source Serif 4", Georgia, serif !important;
  color: var(--dm-ink) !important;
  letter-spacing: -0.02em;
}

[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stChatMessage"] p,
[data-testid="stChatMessage"] li,
[data-testid="stChatMessage"] span,
.stMarkdown, .stCaption, label {
  color: var(--dm-ink) !important;
}
a { color: var(--dm-accent) !important; }

.stButton > button {
  border-radius: 10px !important;
  border: 1px solid var(--dm-line) !important;
  background: var(--dm-surface) !important;
  color: var(--dm-ink) !important;
  font-weight: 600 !important;
  box-shadow: none !important;
}
.stButton > button:hover {
  border-color: var(--dm-accent) !important;
  color: var(--dm-accent) !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
  background: var(--dm-accent) !important;
  color: #fff !important;
  border: none !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--dm-accent-hover) !important;
  color: #fff !important;
}

[data-testid="stFileUploaderDropzone"],
[data-testid="stChatInput"],
.stTextInput input {
  background: var(--dm-surface) !important;
  color: var(--dm-ink) !important;
  border-color: var(--dm-line) !important;
  border-radius: 12px !important;
}
[data-testid="stChatInput"] {
  box-shadow: var(--dm-shadow);
}

div[data-testid="stChatMessage"] {
  background: var(--dm-surface) !important;
  border: 1px solid var(--dm-line) !important;
  border-radius: var(--dm-radius) !important;
  box-shadow: var(--dm-shadow);
  padding: .4rem .55rem;
  margin-bottom: .7rem;
}

.brand-title {
  font-family: "Source Serif 4", Georgia, serif;
  font-weight: 700;
  font-size: 1.35rem;
  color: var(--dm-ink);
  margin: 0;
  letter-spacing: -0.02em;
}
.brand-hero {
  font-family: "Source Serif 4", Georgia, serif;
  font-weight: 700;
  font-size: 0.95rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--dm-accent) !important;
  text-align: center;
  margin: 0.4rem 0 0.2rem;
}
.brand-tag {
  color: var(--dm-muted) !important;
  font-size: .82rem;
  margin: .2rem 0 .8rem;
}
.nav-hint {
  font-size: .7rem;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--dm-muted) !important;
  margin: .85rem 0 .4rem;
}
.hero-title {
  font-family: "Source Serif 4", Georgia, serif;
  font-size: 2rem;
  font-weight: 700;
  letter-spacing: -0.03em;
  color: var(--dm-ink) !important;
  margin: 1.5rem 0 .4rem;
  text-align: center;
}
.hero-sub {
  color: var(--dm-muted) !important;
  text-align: center;
  margin: 0 auto 1.4rem;
  max-width: 34rem;
  font-size: 1rem;
}
.suggest-card {
  border: 1px solid var(--dm-line);
  background: var(--dm-surface);
  border-radius: 12px;
  padding: .9rem 1rem;
  min-height: 4.2rem;
  box-shadow: var(--dm-shadow);
  color: var(--dm-ink);
  font-size: .92rem;
  line-height: 1.4;
}
.source-card {
  border: 1px solid var(--dm-line);
  background: var(--dm-surface);
  border-radius: 12px;
  padding: .85rem 1rem;
  margin-bottom: .55rem;
  box-shadow: var(--dm-shadow);
  color: var(--dm-ink);
}
.source-card .meta {
  color: var(--dm-muted) !important;
  font-size: .78rem;
  margin: .15rem 0 .45rem;
}
.meta-chip {
  display: inline-block;
  padding: .18rem .55rem;
  border-radius: 999px;
  background: var(--dm-accent-soft);
  color: var(--dm-accent) !important;
  font-weight: 650;
  font-size: .72rem;
  margin-right: .35rem;
}
.conf-bar {
  height: 6px;
  border-radius: 999px;
  background: var(--dm-surface-2);
  overflow: hidden;
  margin: .35rem 0 .15rem;
  max-width: 220px;
}
.conf-bar > span {
  display: block;
  height: 100%;
  background: var(--dm-accent);
}
.doc-card {
  border: 1px solid var(--dm-line);
  background: var(--dm-surface);
  border-radius: 12px;
  padding: 1rem 1.1rem;
  margin-bottom: .75rem;
  box-shadow: var(--dm-shadow);
}
.status-ok { color: var(--dm-ok) !important; font-weight: 650; }
.status-warn { color: var(--dm-warn) !important; font-weight: 650; }
.status-err { color: var(--dm-danger) !important; font-weight: 650; }
.mode-banner,
.mode-banner * {
  border: 1px solid #b7d4cc !important;
  background: #e8f5f1 !important;
  color: #14352e !important;
  border-radius: 10px;
  padding: .55rem .8rem;
  font-size: .85rem;
  margin-bottom: .9rem;
}
.mode-banner code {
  background: #d7ebe4 !important;
  color: #0f3d34 !important;
  padding: .05rem .3rem;
  border-radius: 4px;
}
/* Do not force stAlert text colors — Streamlit theme handles info/warning/error */
[data-testid="stAlert"] {
  border-radius: 10px !important;
}
.stage-ok { color: var(--dm-ok) !important; }
.stage-line { font-size: .9rem; margin: .2rem 0; color: var(--dm-ink) !important; }
</style>
"""

DARK_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600;700&family=Source+Serif+4:opsz,wght@8..60,600;8..60,700&display=swap');

:root {
  --dm-bg: #14181d;
  --dm-surface: #1c2229;
  --dm-surface-2: #262d36;
  --dm-ink: #e8edf2;
  --dm-ink-soft: #c5ced8;
  --dm-muted: #9aa6b2;
  --dm-line: #2d3640;
  --dm-accent: #3dba9a;
  --dm-accent-soft: rgba(61,186,154,.14);
  --dm-accent-hover: #56d0b0;
  --dm-danger: #f97066;
  --dm-warn: #fdb022;
  --dm-ok: #47cd89;
  --dm-user: #243039;
  --dm-radius: 12px;
  --dm-shadow: 0 1px 2px rgba(0,0,0,.25);
}

html, body, .stApp, [data-testid="stAppViewContainer"],
[data-testid="stMarkdownContainer"], [data-testid="stMarkdownContainer"] p,
label, .stCaption {
  font-family: "IBM Plex Sans", "Segoe UI", sans-serif !important;
}

.stApp {
  background: var(--dm-bg) !important;
  color: var(--dm-ink) !important;
}

/* Hide Streamlit chrome that overlaps page content (Deploy / menu bar) */
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
  padding-top: 1.75rem !important;
  padding-bottom: 2.5rem !important;
  max-width: 1120px !important;
}

section.main {
  padding-top: 0.5rem !important;
}

[data-testid="stSidebar"] {
  background: #171c22 !important;
  border-right: 1px solid var(--dm-line) !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] span,
[data-testid="stSidebar"] p {
  color: var(--dm-ink) !important;
}
[data-testid="stSidebar"] .stCaption,
[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {
  color: var(--dm-muted) !important;
}

h1,h2,h3,.stMarkdown h1,.stMarkdown h2,.stMarkdown h3 {
  font-family: "Source Serif 4", Georgia, serif !important;
  color: var(--dm-ink) !important;
}

[data-testid="stMarkdownContainer"],
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] li,
[data-testid="stChatMessage"],
[data-testid="stChatMessage"] *,
[data-testid="stChatMessage"] p,
.stMarkdown, .stCaption, label,
[data-testid="stMetricValue"],
[data-testid="stMetricLabel"] {
  color: var(--dm-ink) !important;
}
a { color: #6ee7c5 !important; }

.stButton > button {
  border-radius: 10px !important;
  border: 1px solid var(--dm-line) !important;
  background: var(--dm-surface-2) !important;
  color: var(--dm-ink) !important;
  font-weight: 600 !important;
}
.stButton > button:hover {
  border-color: var(--dm-accent) !important;
}
.stButton > button[kind="primary"],
.stButton > button[data-testid="baseButton-primary"] {
  background: var(--dm-accent) !important;
  color: #0b1613 !important;
  border: none !important;
}

[data-testid="stFileUploaderDropzone"],
[data-testid="stChatInput"],
.stTextInput input,
[data-testid="stExpander"] {
  background: var(--dm-surface) !important;
  color: var(--dm-ink) !important;
  border-color: var(--dm-line) !important;
  border-radius: 12px !important;
}
[data-testid="stFileUploaderDropzone"] * {
  color: var(--dm-ink-soft) !important;
}
[data-testid="stChatInput"] { box-shadow: var(--dm-shadow); }

div[data-testid="stChatMessage"] {
  background: var(--dm-surface) !important;
  border: 1px solid var(--dm-line) !important;
  border-radius: var(--dm-radius) !important;
  margin-bottom: .7rem;
}

.brand-title {
  font-family: "Source Serif 4", Georgia, serif;
  font-weight: 700;
  font-size: 1.35rem;
  color: var(--dm-ink) !important;
  margin: 0;
}
.brand-hero {
  font-family: "Source Serif 4", Georgia, serif;
  font-weight: 700;
  font-size: 0.95rem;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--dm-accent) !important;
  text-align: center;
  margin: 0.4rem 0 0.2rem;
}
.brand-tag {
  color: var(--dm-muted) !important;
  font-size: .82rem;
  margin: .2rem 0 .8rem;
}
.nav-hint {
  font-size: .7rem;
  font-weight: 700;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--dm-muted) !important;
  margin: .85rem 0 .4rem;
}
.hero-title {
  font-family: "Source Serif 4", Georgia, serif;
  font-size: 2rem;
  font-weight: 700;
  color: var(--dm-ink) !important;
  margin: 1.5rem 0 .4rem;
  text-align: center;
}
.hero-sub {
  color: var(--dm-muted) !important;
  text-align: center;
  margin: 0 auto 1.4rem;
  max-width: 34rem;
}
.suggest-card, .source-card, .doc-card {
  border: 1px solid var(--dm-line);
  background: var(--dm-surface);
  border-radius: 12px;
  color: var(--dm-ink) !important;
  box-shadow: var(--dm-shadow);
}
.suggest-card { padding: .9rem 1rem; min-height: 4.2rem; font-size: .92rem; }
.source-card { padding: .85rem 1rem; margin-bottom: .55rem; }
.source-card .meta { color: var(--dm-muted) !important; font-size: .78rem; margin: .15rem 0 .45rem; }
.doc-card { padding: 1rem 1.1rem; margin-bottom: .75rem; }
.mode-banner,
.mode-banner * {
  border: 1px solid #2f5f52 !important;
  background: #1a2f29 !important;
  color: #d8f3ea !important;
  border-radius: 10px;
  padding: .55rem .8rem;
  font-size: .85rem;
  margin-bottom: .9rem;
}
.mode-banner code {
  background: #243f37 !important;
  color: #9af0d5 !important;
}
[data-testid="stAlert"] {
  border-radius: 10px !important;
}
.meta-chip {
  display: inline-block;
  padding: .18rem .55rem;
  border-radius: 999px;
  background: var(--dm-accent-soft);
  color: #9af0d5 !important;
  font-weight: 650;
  font-size: .72rem;
  margin-right: .35rem;
}
.conf-bar {
  height: 6px;
  border-radius: 999px;
  background: var(--dm-surface-2);
  overflow: hidden;
  margin: .35rem 0 .15rem;
  max-width: 220px;
}
.conf-bar > span { display: block; height: 100%; background: var(--dm-accent); }
.status-ok { color: var(--dm-ok) !important; font-weight: 650; }
.status-warn { color: var(--dm-warn) !important; font-weight: 650; }
.status-err { color: var(--dm-danger) !important; font-weight: 650; }
.stage-ok { color: var(--dm-ok) !important; }
.stage-line { font-size: .9rem; margin: .2rem 0; color: var(--dm-ink) !important; }
</style>
"""


def apply_theme(dark: bool) -> str:
    return DARK_CSS if dark else LIGHT_CSS
