"""Tests for PDF loading and chunking.

These use the committed sample PDFs, so they exercise real pypdf extraction
(including umlauts) rather than mocked text.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from pdfragen.config import get_config
from pdfragen.ingestion import chunk_documents, chunk_stats, load_pdf

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
SAMPLE = EXAMPLES / "auslaenderbehoerde_verlaengerung.pdf"


def test_load_pdf_returns_one_document_per_page() -> None:
    pages = load_pdf(SAMPLE)
    assert len(pages) == 2
    assert [p.metadata["page"] for p in pages] == [0, 1]


def test_load_pdf_preserves_umlauts() -> None:
    text = load_pdf(SAMPLE)[0].page_content
    assert "Ausländerbehörde" in text
    assert "Verlängerung" in text


def test_load_pdf_missing_file() -> None:
    with pytest.raises(FileNotFoundError):
        load_pdf(EXAMPLES / "does_not_exist.pdf")


def test_load_pdf_rejects_non_pdf(tmp_path: Path) -> None:
    bad = tmp_path / "not_really.pdf"
    bad.write_text("this is plain text, not a PDF")
    with pytest.raises(ValueError, match="Could not read"):
        load_pdf(bad)


def test_chunks_inherit_page_metadata() -> None:
    chunks = chunk_documents(load_pdf(SAMPLE), get_config())
    assert chunks
    for chunk in chunks:
        assert chunk.metadata["page"] in (0, 1)
        assert "source" in chunk.metadata


def test_chunks_respect_configured_size() -> None:
    cfg = get_config()
    chunks = chunk_documents(load_pdf(SAMPLE), cfg)
    assert max(len(c.page_content) for c in chunks) <= cfg.chunk_size


def test_chunk_stats_on_empty_input() -> None:
    stats = chunk_stats([])
    assert stats.num_chunks == 0
    assert stats.avg_chars == 0.0
