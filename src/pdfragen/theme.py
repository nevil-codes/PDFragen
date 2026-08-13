"""Presentation-layer styling for the Streamlit app.

Holds the design tokens and the injected CSS so ``app.py`` stays readable.
Nothing here touches the RAG pipeline — it is purely how the app looks.
"""

from __future__ import annotations

# Design tokens. Names match the mockup's palette labels.
ACCENT = "#2F5D5B"
ACCENT_DARK = "#254A48"
ACCENT_TINT = "#E6EEEC"
CITATION = "#EFE7D8"
CITATION_INK = "#6B5B3E"
INK = "#1D2321"
SIDEBAR = "#F5F2EC"
PAPER = "#FDFCFA"
LINE = "#E4DED3"
LINE_SOFT = "#DCD5C9"
BODY = "#4A524E"
MUTED = "#8A9088"
MUTED_SOFT = "#A5A9A2"
SUBTLE = "#5D655F"
NOTICE_BG = "#FBF6EC"
NOTICE_LINE = "#E0D3C0"

SERIF = "'Source Serif 4', Georgia, serif"
SANS = "'IBM Plex Sans', system-ui, sans-serif"
MONO = "'IBM Plex Mono', ui-monospace, monospace"

FONT_IMPORT = (
    "@import url('https://fonts.googleapis.com/css2?"
    "family=Source+Serif+4:opsz,wght@8..60,400;8..60,600"
    "&family=IBM+Plex+Sans:wght@400;500;600"
    "&family=IBM+Plex+Mono:wght@400;500&display=swap');"
)


def page_css() -> str:
    """Return the app's stylesheet, ready to inject inside a ``<style>`` tag."""
    return f"""
{FONT_IMPORT}

:root {{
  --accent: {ACCENT};
  --ink: {INK};
  --line: {LINE};
  --muted: {MUTED};
}}

/* ---- shell ---- */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stMain"],
[data-testid="stBottom"],
[data-testid="stBottomBlockContainer"] {{
  background: {PAPER};
  color: {INK};
  font-family: {SANS};
  -webkit-font-smoothing: antialiased;
}}
[data-testid="stHeader"] {{ background: transparent; }}
.block-container {{
  max-width: 730px;
  padding-top: 2.2rem;
  padding-bottom: 1rem;
}}
[data-testid="stBottom"] {{ border-top: 1px solid {LINE}; }}
#MainMenu, footer, [data-testid="stStatusWidget"], [data-testid="stDecoration"],
[data-testid="stAppDeployButton"], [data-testid="stToolbar"] {{
  display: none;
}}

/* ---- sidebar ---- */
[data-testid="stSidebar"] {{
  background: {SIDEBAR};
  border-right: 1px solid {LINE};
  width: 288px !important;
}}
[data-testid="stSidebar"] > div {{ padding-top: 1.6rem; }}

/* ---- typography ---- */
.pf-display {{
  font-family: {SERIF};
  font-weight: 600;
  font-size: 34px;
  line-height: 1.15;
  letter-spacing: -0.015em;
  color: {INK};
  margin: 0 0 12px;
  text-wrap: pretty;
}}
.pf-lede {{
  font-size: 15.5px;
  line-height: 1.6;
  color: {SUBTLE};
  margin: 0;
  text-wrap: pretty;
}}
.pf-eyebrow {{
  font-family: {MONO};
  font-size: 10px;
  letter-spacing: 0.1em;
  color: {MUTED};
  text-transform: uppercase;
  margin: 0 0 8px;
}}
.pf-brand {{
  display: flex; align-items: center; gap: 10px; margin-bottom: 22px;
}}
.pf-brand-mark {{
  width: 26px; height: 26px; border-radius: 6px; background: {ACCENT};
  display: flex; align-items: center; justify-content: center;
  font-family: {SERIF}; font-weight: 600; font-size: 14px; color: {SIDEBAR};
}}
.pf-brand-name {{ font-family: {SERIF}; font-weight: 600; font-size: 19px; }}

/* ---- cards ---- */
.pf-doc-card {{
  background: #FFFFFF; border: 1px solid {ACCENT}; border-radius: 8px;
  padding: 11px 12px; display: flex; flex-direction: column; gap: 5px;
}}
.pf-doc-name {{
  font-size: 13px; font-weight: 500; color: {INK};
  overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
}}
.pf-doc-meta {{
  font-family: {MONO}; font-size: 10px; color: {MUTED}; letter-spacing: 0.04em;
}}
.pf-empty-card {{
  border: 1px dashed #D3CBBD; border-radius: 8px; padding: 18px 14px;
  text-align: center; color: {MUTED}; font-size: 13px; line-height: 1.5;
}}
.pf-hint {{
  display: flex; align-items: flex-start; gap: 8px; background: {ACCENT_TINT};
  border-radius: 7px; padding: 10px 11px; margin-top: 10px;
}}
.pf-hint-tag {{
  font-family: {MONO}; font-size: 9.5px; letter-spacing: 0.06em;
  background: {ACCENT}; color: {SIDEBAR}; border-radius: 3px;
  padding: 2px 5px; flex: 0 0 auto;
}}
.pf-hint-text {{ font-size: 11.5px; line-height: 1.5; color: #2F4A48; }}
.pf-sidebar-foot {{
  font-family: {MONO}; font-size: 10px; color: {MUTED_SOFT};
  letter-spacing: 0.05em; line-height: 1.7; margin-top: 26px;
  padding-top: 16px; border-top: 1px solid {LINE};
}}

/* ---- example prompts ---- */
.pf-example {{
  background: #FFFFFF; border: 1px solid {LINE}; border-radius: 9px;
  padding: 14px 16px; height: 100%;
}}
.pf-example-q {{ font-size: 13.5px; line-height: 1.45; color: {INK}; }}
.pf-example-tag {{
  font-family: {MONO}; font-size: 10px; color: {MUTED};
  letter-spacing: 0.04em; margin-top: 6px;
}}

/* ---- document header bar ---- */
.pf-docbar {{
  display: flex; align-items: center; gap: 10px; flex-wrap: wrap;
  border-bottom: 1px solid {LINE}; padding-bottom: 13px; margin-bottom: 20px;
}}
.pf-docbar-tag {{
  font-family: {MONO}; font-size: 9.5px; letter-spacing: 0.06em;
  color: {ACCENT}; background: {ACCENT_TINT}; border-radius: 3px; padding: 3px 6px;
}}
.pf-docbar-name {{ font-size: 13.5px; font-weight: 500; }}
.pf-docbar-meta {{
  font-family: {MONO}; font-size: 10.5px; color: {MUTED}; letter-spacing: 0.04em;
}}

/* ---- chat ---- */
[data-testid="stChatMessage"] {{
  background: transparent; padding: 0.4rem 0 0.2rem; gap: 14px;
}}
[data-testid="stChatMessageContent"] p {{
  font-size: 14.5px; line-height: 1.65; color: {INK};
}}
[data-testid="stChatMessageContent"] li {{
  font-size: 14.5px; line-height: 1.6; color: {INK};
}}
.pf-role {{
  display: flex; align-items: center; gap: 8px; margin-bottom: 2px;
}}
.pf-role-name {{ font-size: 12.5px; font-weight: 500; color: {BODY}; }}
.pf-lang-chip {{
  font-family: {MONO}; font-size: 9.5px; letter-spacing: 0.06em;
  border-radius: 3px; padding: 1px 5px;
  color: {MUTED}; border: 1px solid {LINE};
}}
.pf-lang-chip.de {{
  color: {ACCENT}; background: {ACCENT_TINT}; border-color: #CFDEDB;
}}

/* ---- citation pills ---- */
.pf-sources {{
  display: flex; flex-wrap: wrap; gap: 8px; align-items: center;
  margin-top: 12px;
}}
.pf-pill {{
  display: inline-flex; align-items: center; gap: 8px; background: #FFFFFF;
  border: 1px solid {LINE_SOFT}; border-radius: 999px; padding: 5px 12px 5px 9px;
}}
.pf-pill-page {{
  font-family: {MONO}; font-size: 9.5px; background: {CITATION};
  color: {CITATION_INK}; border-radius: 3px; padding: 2px 5px;
  letter-spacing: 0.04em; flex: 0 0 auto;
}}
.pf-pill-file {{
  font-family: {MONO}; font-size: 10.5px; color: {BODY}; letter-spacing: 0.02em;
}}
.pf-caveat {{
  font-family: {MONO}; font-size: 10px; color: {MUTED_SOFT}; letter-spacing: 0.04em;
}}
.pf-notice {{
  border: 1px solid {NOTICE_LINE}; background: {NOTICE_BG}; border-radius: 8px;
  padding: 12px 14px; font-size: 12.5px; line-height: 1.55; color: {CITATION_INK};
}}

/* ---- source expander ---- */
[data-testid="stExpander"] details {{
  border: 1px solid {LINE}; border-radius: 8px; background: #FBFAF7;
}}
[data-testid="stExpander"] summary {{
  font-family: {MONO}; font-size: 10px; letter-spacing: 0.08em;
  color: {MUTED}; text-transform: uppercase;
}}
.pf-passage {{
  font-family: {SERIF}; font-size: 14px; line-height: 1.6; color: {INK};
  border-left: 2px solid {CITATION}; padding-left: 12px; margin: 2px 0 14px;
}}
.pf-passage-head {{
  font-family: {MONO}; font-size: 10px; letter-spacing: 0.08em;
  color: {MUTED}; margin-bottom: 5px;
}}

/* ---- controls ---- */
[data-testid="stFileUploaderDropzone"] {{
  background: #FAF7F1; border: 1.5px dashed #C7BEAE; border-radius: 12px;
}}
[data-testid="stFileUploaderDropzone"] button {{
  background: {ACCENT}; color: #F7F5F0; border: none; border-radius: 7px;
  font-family: {SANS}; font-size: 13.5px; font-weight: 500;
}}
[data-testid="stFileUploaderDropzone"] button:hover {{ background: {ACCENT_DARK}; }}
[data-baseweb="segmented-control"], [role="radiogroup"] {{ gap: 0; }}
[data-testid="stChatInput"] {{
  border: 1px solid #C7BEAE; border-radius: 9px; background: #FFFFFF;
}}
[data-testid="stChatInput"] textarea {{ font-size: 14px; }}
.pf-input-caption {{
  font-family: {MONO}; font-size: 10px; color: {MUTED_SOFT};
  letter-spacing: 0.05em; margin-top: 8px; line-height: 1.5;
}}
.stButton button {{
  border-radius: 6px; border: 1px solid {LINE_SOFT}; background: #FFFFFF;
  color: {BODY}; font-size: 13px; font-weight: 400;
}}
.stButton button:hover {{ border-color: {ACCENT}; color: {ACCENT}; }}
"""


def avatar(letter: str, background: str, color: str, serif: bool = True) -> str:
    """Build a data-URI SVG avatar.

    Streamlit's ``st.chat_message(avatar=...)`` takes an image; an inline SVG
    keeps the lettered marks from the mockup without shipping image assets or
    falling back to emoji.

    Args:
        letter: One or two characters to draw.
        background: Circle fill colour.
        color: Text colour.
        serif: Whether to letter it in the display serif.

    Returns:
        A ``data:image/svg+xml`` URI.
    """
    import urllib.parse

    family = "Georgia,serif" if serif else "ui-monospace,monospace"
    size = 15 if len(letter) == 1 else 12
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32">'
        f'<circle cx="16" cy="16" r="16" fill="{background}"/>'
        f'<text x="16" y="16" text-anchor="middle" dominant-baseline="central" '
        f'font-family="{family}" font-size="{size}" font-weight="600" '
        f'fill="{color}">{letter}</text></svg>'
    )
    return "data:image/svg+xml;charset=utf-8," + urllib.parse.quote(svg)
