"""styles.css must not hardcode colours outside @@tokens blocks."""

from __future__ import annotations

import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "streamlit_app" / "styles" / "styles.css"

_HEX = re.compile(r"#[0-9A-Fa-f]{3,8}\b")
_RGB = re.compile(r"rgba?\([^)]*\)", re.I)
# Named CSS colours (common set) — allow transparent/inherit/currentcolor/none
_NAMED = re.compile(
    r"(?<![\w-])(white|black|red|blue|green|gray|grey|navy|teal|silver|"
    r"maroon|olive|purple|fuchsia|aqua|lime|yellow|orange|pink|cyan|"
    r"magenta|violet|indigo|brown|coral|crimson|gold|ivory|khaki|lavender|"
    r"linen|salmon|tan|tomato|turquoise|wheat|azure|beige|bisque|snow)"
    r"(?![\w-])",
    re.I,
)
_TOKEN_BLOCKS = re.compile(
    r"/\* @@tokens:(?:light|dark) \*/.*?/\* @@/tokens:(?:light|dark) \*/",
    re.S,
)


def _strip_tokens(text: str) -> str:
    return _TOKEN_BLOCKS.sub("", text)


def _strip_comments(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def test_styles_css_exists():
    assert CSS.is_file(), f"missing {CSS}"


def test_no_hardcoded_colours_outside_tokens():
    raw = CSS.read_text(encoding="utf-8")
    assert "@@tokens:light" in raw and "@@tokens:dark" in raw
    body = _strip_comments(_strip_tokens(raw))
    hexes = _HEX.findall(body)
    rgbs = _RGB.findall(body)
    named = _NAMED.findall(body)
    assert not hexes, f"hex outside tokens: {hexes[:10]}"
    assert not rgbs, f"rgb/rgba outside tokens: {rgbs[:10]}"
    assert not named, f"named colours outside tokens: {named[:10]}"


def test_required_token_names_present():
    raw = CSS.read_text(encoding="utf-8")
    required = [
        "--dm-background",
        "--dm-surface",
        "--dm-surface-raised",
        "--dm-border",
        "--dm-text",
        "--dm-text-muted",
        "--dm-accent",
        "--dm-accent-text",
        "--dm-danger",
        "--dm-warning",
    ]
    for name in required:
        assert name in raw, f"missing token {name}"


def test_apply_theme_switches_sets():
    import importlib.util

    theme_path = CSS.parent / "theme.py"
    spec = importlib.util.spec_from_file_location("dm_theme", theme_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    light = mod.apply_theme(False)
    dark = mod.apply_theme(True)
    assert "#F8FAFC" in light and "--dm-background" in light
    assert "#0B1220" in dark and "--dm-background" in dark
    assert "var(--dm-text)" in light
    assert "var(--dm-border)" in dark
