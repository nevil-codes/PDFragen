"""Streamlit chat UI for PDFragen.

Upload a German-language PDF, ask questions about it in English or German,
and see answers grounded in the document with page citations. Run with:

    streamlit run app.py
"""

from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

import streamlit as st

from pdfragen.config import get_config
from pdfragen.rag import answer
from pdfragen.vectorstore import add_chunks, get_vectorstore
from pdfragen.ingestion import ingest

st.set_page_config(page_title="PDFragen", page_icon="📄")
st.title("📄 PDFragen")
st.caption(
    "Upload a German document and ask questions about it in English or Deutsch."
)

with st.sidebar:
    st.header("Document")
    uploaded_file = st.file_uploader("Upload a PDF", type="pdf")

    st.header("Answer language")
    language_choice = st.radio(
        "Force answer language",
        options=["Auto (match question)", "English", "Deutsch"],
        index=0,
    )
    forced_language = None if language_choice.startswith("Auto") else language_choice

if "session_dir" not in st.session_state:
    st.session_state.session_dir = tempfile.mkdtemp(prefix="pdfragen_")
if "ingested_hash" not in st.session_state:
    st.session_state.ingested_hash = None
if "messages" not in st.session_state:
    st.session_state.messages = []

cfg = get_config()


def _ingest_upload(file) -> None:
    """Save, load, chunk, embed, and store an uploaded PDF for this session."""
    file_bytes = file.getvalue()
    file_hash = hashlib.sha1(file_bytes).hexdigest()[:12]

    if st.session_state.ingested_hash == file_hash:
        return

    pdf_path = Path(st.session_state.session_dir) / file.name
    pdf_path.write_bytes(file_bytes)

    session_cfg = cfg.__class__(
        **{
            **cfg.__dict__,
            "chroma_dir": st.session_state.session_dir,
            "collection_name": f"pdfragen_{file_hash}",
        }
    )

    with st.spinner(f"Reading and indexing {file.name}..."):
        chunks = ingest(pdf_path, session_cfg)
        store = get_vectorstore(session_cfg)
        add_chunks(chunks, session_cfg, store)

    st.session_state.ingested_hash = file_hash
    st.session_state.session_cfg = session_cfg
    st.session_state.messages = []
    st.success(f"Indexed {file.name} ({len(chunks)} chunks).")


if uploaded_file is not None:
    try:
        _ingest_upload(uploaded_file)
    except ValueError as exc:
        st.error(str(exc))
        st.stop()

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("sources"):
            with st.expander("Sources"):
                for src in message["sources"]:
                    st.markdown(f"**Page {src.page}:** {src.text[:300]}...")

if st.session_state.ingested_hash is None:
    st.info("Upload a PDF in the sidebar to start asking questions.")
else:
    question = st.chat_input("Ask a question about the document (EN or DE)...")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    result = answer(
                        question,
                        st.session_state.session_cfg,
                        language=forced_language,
                    )
                    st.markdown(result.text)
                    if result.sources:
                        with st.expander("Sources"):
                            for src in result.sources:
                                st.markdown(f"**Page {src.page}:** {src.text[:300]}...")
                    st.session_state.messages.append(
                        {
                            "role": "assistant",
                            "content": result.text,
                            "sources": result.sources,
                        }
                    )
                except ConnectionError as exc:
                    st.error(str(exc))
