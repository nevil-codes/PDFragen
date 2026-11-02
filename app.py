"""Streamlit chat UI for PDFragen.

Upload a German-language PDF, ask questions about it in English or German,
and see answers grounded in the document with page citations. Run with:

    streamlit run app.py
"""

from __future__ import annotations

import hashlib
import html
import re
import tempfile
from pathlib import Path

import streamlit as st

from pdfragen import theme
from pdfragen.config import get_config
from pdfragen.ingestion import ingest
from pdfragen.rag import answer, check_ollama
from pdfragen.vectorstore import add_chunks, get_vectorstore

st.set_page_config(
    page_title="PDFragen",
    layout="centered",
    initial_sidebar_state="expanded",
)
st.markdown(f"<style>{theme.page_css()}</style>", unsafe_allow_html=True)

USER_AVATAR = theme.avatar("Du", theme.LINE, theme.SUBTLE, serif=False)
BOT_AVATAR = theme.avatar("P", theme.ACCENT, theme.SIDEBAR)

EXAMPLE_PROMPTS = [
    ("“What is the deadline in this letter?”", "Deadlines & dates"),
    ("„Welche Unterlagen muss ich mitbringen?“", "Required documents"),
    ("“Explain this paragraph in simple English.”", "Plain-language rewrite"),
    ("„Worum geht es in diesem Abschnitt?“", "Coursework"),
]

# Function words and orthography that only appear in German. Used purely to
# label a message EN or DE in the transcript — it never changes retrieval or
# generation, which handle either language on their own.
_GERMAN_MARKERS = re.compile(
    r"[äöüß]|\b(der|die|das|und|ist|nicht|ich|wie|was|wann|wo|muss|kann|"
    r"welche|warum|mein|meine|für|mit|von|auf|bis|dem|den|ein|eine|wird)\b",
    re.IGNORECASE,
)


def detect_language(text: str) -> str:
    """Label ``text`` as German or English for display purposes.

    Args:
        text: The user's question.

    Returns:
        ``"DE"`` if German markers are present, otherwise ``"EN"``.
    """
    return "DE" if len(_GERMAN_MARKERS.findall(text)) >= 2 else "EN"


def page_label(page: int | str, language: str) -> str:
    """Format a page badge in the reader's language (``S. 2`` vs ``p. 2``)."""
    prefix = "S." if language == "DE" else "p."
    return f"{prefix} {page if page == '?' else int(page) + 1}"


def truncate_filename(name: str, limit: int = 26) -> str:
    """Shorten a filename with a middle ellipsis, per the citation pill spec."""
    if len(name) <= limit:
        return name
    keep = (limit - 1) // 2
    return f"{name[:keep]}…{name[-keep:]}"


def render_sources(sources, filename: str, language: str) -> None:
    """Render citation pills plus an expander holding the full passages.

    Pills are deduplicated by page so a question matching several chunks on
    one page cites that page once.

    Args:
        sources: ``Source`` records returned alongside an answer.
        filename: Name of the indexed document, shown inside each pill.
        language: ``"EN"`` or ``"DE"``, controls the page-label prefix.
    """
    if not sources:
        return

    # Deduplicate, then read in page order rather than retrieval-score order.
    seen = sorted(
        {src.page for src in sources},
        key=lambda page: (page == "?", page if page != "?" else 0),
    )

    short = html.escape(truncate_filename(filename))
    pills = "".join(
        f'<span class="pf-pill">'
        f'<span class="pf-pill-page">{page_label(page, language)}</span>'
        f'<span class="pf-pill-file">{short}</span></span>'
        for page in seen
    )
    st.markdown(
        f'<div class="pf-sources">{pills}'
        f'<span class="pf-caveat">· not legal advice</span></div>',
        unsafe_allow_html=True,
    )

    with st.expander("Read the cited passages"):
        for src in sources:
            st.markdown(
                f'<div class="pf-passage-head">{page_label(src.page, language)}</div>'
                f'<div class="pf-passage">{html.escape(src.text.strip())}</div>',
                unsafe_allow_html=True,
            )


def render_role(name: str, language: str | None = None) -> None:
    """Render a message's author line with an optional EN/DE chip."""
    chip = ""
    if language:
        css = "pf-lang-chip de" if language == "DE" else "pf-lang-chip"
        chip = f'<span class="{css}">{language}</span>'
    st.markdown(
        f'<div class="pf-role"><span class="pf-role-name">{name}</span>{chip}</div>',
        unsafe_allow_html=True,
    )


# --- session state ----------------------------------------------------------

if "session_dir" not in st.session_state:
    st.session_state.session_dir = tempfile.mkdtemp(prefix="pdfragen_")
if "ingested_hash" not in st.session_state:
    st.session_state.ingested_hash = None
if "messages" not in st.session_state:
    st.session_state.messages = []
if "doc_name" not in st.session_state:
    st.session_state.doc_name = None
if "doc_pages" not in st.session_state:
    st.session_state.doc_pages = 0

cfg = get_config()


def ingest_upload(file) -> None:
    """Save, load, chunk, embed, and store an uploaded PDF for this session."""
    file_bytes = file.getvalue()
    file_hash = hashlib.sha1(file_bytes).hexdigest()[:12]

    if st.session_state.ingested_hash == file_hash:
        return

    # .name drops any directory part, so "../../x.pdf" can't escape the session dir.
    pdf_path = Path(st.session_state.session_dir) / Path(file.name).name
    pdf_path.write_bytes(file_bytes)

    session_cfg = cfg.__class__(
        **{
            **cfg.__dict__,
            "chroma_dir": st.session_state.session_dir,
            "collection_name": f"pdfragen_{file_hash}",
        }
    )

    with st.spinner(f"Reading and indexing {file.name}…"):
        chunks = ingest(pdf_path, session_cfg)
        store = get_vectorstore(session_cfg)
        add_chunks(chunks, session_cfg, store)

    st.session_state.ingested_hash = file_hash
    st.session_state.session_cfg = session_cfg
    st.session_state.messages = []
    st.session_state.doc_name = file.name
    st.session_state.doc_pages = max(int(c.metadata.get("page", 0)) for c in chunks) + 1


# --- sidebar ----------------------------------------------------------------

with st.sidebar:
    st.markdown(
        '<div class="pf-brand"><div class="pf-brand-mark">P</div>'
        '<div class="pf-brand-name">PDFragen</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="pf-eyebrow">Your document</div>', unsafe_allow_html=True)
    if st.session_state.doc_name:
        st.markdown(
            f'<div class="pf-doc-card">'
            f'<div class="pf-doc-name">{html.escape(st.session_state.doc_name)}</div>'
            f'<div class="pf-doc-meta">{st.session_state.doc_pages} pages · indexed</div>'
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            '<div class="pf-empty-card">No document yet.<br>Upload a PDF to begin.</div>',
            unsafe_allow_html=True,
        )

    # Before any upload the drop zone is the main column's job (it is the whole
    # screen at that point); afterwards it lives here, next to the document card.
    if st.session_state.ingested_hash is not None:
        uploaded_file = st.file_uploader(
            "Replace the document", type="pdf", label_visibility="collapsed"
        )
    else:
        uploaded_file = None

    st.markdown(
        '<div class="pf-eyebrow" style="margin-top:18px">Answer language</div>',
        unsafe_allow_html=True,
    )
    indexed = st.session_state.ingested_hash is not None
    language_choice = st.segmented_control(
        "Answer language",
        options=["Auto", "English", "Deutsch"],
        default="Auto",
        disabled=not indexed,
        label_visibility="collapsed",
    )
    forced_language = None if language_choice in (None, "Auto") else language_choice

    st.markdown(
        '<div class="pf-hint"><span class="pf-hint-tag">EN/DE</span>'
        '<span class="pf-hint-text">Ask in either language. Auto answers in the '
        "one you used.</span></div>",
        unsafe_allow_html=True,
    )

    st.markdown(
        f'<div class="pf-sidebar-foot">Retrieval · top-k {cfg.top_k}<br>'
        f"Chunk {cfg.chunk_size} / overlap {cfg.chunk_overlap}<br>"
        f"Runs locally · {cfg.llm_model}</div>",
        unsafe_allow_html=True,
    )

ollama_problem = check_ollama(cfg)
if ollama_problem:
    st.markdown(f'<div class="pf-notice">{ollama_problem}</div>', unsafe_allow_html=True)

# --- main column ------------------------------------------------------------

if st.session_state.ingested_hash is None:
    st.markdown(
        '<h1 class="pf-display">Understand your German documents, '
        "in your language.</h1>"
        '<p class="pf-lede">Upload a university letter, lecture handout or piece of '
        "admin paperwork. Ask about it in English or German — every answer points "
        "back to the exact page it came from.</p>",
        unsafe_allow_html=True,
    )

    st.markdown("<div style='height:22px'></div>", unsafe_allow_html=True)
    uploaded_file = st.file_uploader(
        "Drag a PDF here, or browse your files", type="pdf"
    )

    st.markdown(
        '<div class="pf-eyebrow" style="margin-top:30px">What you can ask it</div>',
        unsafe_allow_html=True,
    )
    for row in (EXAMPLE_PROMPTS[:2], EXAMPLE_PROMPTS[2:]):
        for column, (question, tag) in zip(st.columns(2), row):
            column.markdown(
                f'<div class="pf-example"><div class="pf-example-q">{question}</div>'
                f'<div class="pf-example-tag">{tag}</div></div>',
                unsafe_allow_html=True,
            )

    st.chat_input("Upload a PDF to start asking questions…", disabled=True)

    if uploaded_file is not None:
        try:
            ingest_upload(uploaded_file)
        except ValueError as exc:
            # Unreadable, empty, or image-only PDF — the message says which.
            st.markdown(f'<div class="pf-notice">{html.escape(str(exc))}</div>', unsafe_allow_html=True)
            st.stop()
        except Exception as exc:  # noqa: BLE001 - last resort, keep the UI usable
            st.markdown(
                f'<div class="pf-notice">Could not index {html.escape(uploaded_file.name)}: '
                f"{html.escape(str(exc))}</div>",
                unsafe_allow_html=True,
            )
            st.stop()
        # Swap the landing page for the chat view in one step.
        st.rerun()
else:
    if uploaded_file is not None:
        try:
            ingest_upload(uploaded_file)
        except ValueError as exc:
            st.markdown(f'<div class="pf-notice">{html.escape(str(exc))}</div>', unsafe_allow_html=True)
            st.stop()
        except Exception as exc:  # noqa: BLE001 - last resort, keep the UI usable
            st.markdown(
                f'<div class="pf-notice">Could not index {html.escape(uploaded_file.name)}: '
                f"{html.escape(str(exc))}</div>",
                unsafe_allow_html=True,
            )
            st.stop()

    st.markdown(
        f'<div class="pf-docbar"><span class="pf-docbar-tag">PDF</span>'
        f'<span class="pf-docbar-name">{html.escape(st.session_state.doc_name)}</span>'
        f'<span class="pf-docbar-meta">· {st.session_state.doc_pages} pages</span>'
        f"</div>",
        unsafe_allow_html=True,
    )

    for message in st.session_state.messages:
        avatar = USER_AVATAR if message["role"] == "user" else BOT_AVATAR
        with st.chat_message(message["role"], avatar=avatar):
            render_role(
                "You" if message["role"] == "user" else "PDFragen",
                message.get("lang"),
            )
            st.markdown(message["content"])
            if message.get("sources"):
                render_sources(
                    message["sources"], st.session_state.doc_name, message["lang"]
                )

    question = st.chat_input("Ask about this document — English or German…")
    st.markdown(
        '<div class="pf-input-caption">Answers come only from your uploaded file · '
        "check the cited pages before acting</div>",
        unsafe_allow_html=True,
    )

    if question:
        question_lang = detect_language(question)
        st.session_state.messages.append(
            {"role": "user", "content": question, "lang": question_lang}
        )
        with st.chat_message("user", avatar=USER_AVATAR):
            render_role("You", question_lang)
            st.markdown(question)

        answer_lang = {"English": "EN", "Deutsch": "DE"}.get(
            forced_language, question_lang
        )
        with st.chat_message("assistant", avatar=BOT_AVATAR):
            render_role("PDFragen", answer_lang)
            with st.spinner("Reading the document…"):
                try:
                    result = answer(
                        question,
                        st.session_state.session_cfg,
                        language=forced_language,
                    )
                except ConnectionError as exc:
                    st.markdown(
                        f'<div class="pf-notice">{exc}</div>', unsafe_allow_html=True
                    )
                    st.stop()

            if result.sources:
                st.markdown(result.text)
                render_sources(
                    result.sources, st.session_state.doc_name, answer_lang
                )
            else:
                st.markdown(
                    f'<div class="pf-notice">{result.text}</div>',
                    unsafe_allow_html=True,
                )

            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "content": result.text,
                    "sources": result.sources,
                    "lang": answer_lang,
                }
            )
