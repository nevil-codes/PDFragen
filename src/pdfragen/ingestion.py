"""PDF loading and chunking.

Loads a PDF page-by-page (preserving page numbers for later citations) and
splits it into overlapping chunks sized for German prose. Run as a script to
inspect chunk statistics before wiring the vector store:

    python -m pdfragen.ingestion examples/sample.pdf
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

from langchain_community.document_loaders import PyPDFLoader
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

from pdfragen.config import Config, get_config


def load_pdf(path: str | Path) -> list[Document]:
    """Load a PDF into one LangChain ``Document`` per page.

    Each returned document carries ``metadata['source']`` (file path) and
    ``metadata['page']`` (0-indexed page number), which propagate to chunks and
    are later surfaced as answer citations.

    Args:
        path: Path to the PDF file.

    Returns:
        One ``Document`` per page, in page order.

    Raises:
        FileNotFoundError: If ``path`` does not exist.
        ValueError: If the file has no extractable text (e.g. scanned images).
    """
    pdf_path = Path(path)
    if not pdf_path.is_file():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    pages = PyPDFLoader(str(pdf_path)).load()
    if not any(page.page_content.strip() for page in pages):
        raise ValueError(
            f"No extractable text in {pdf_path}. Is it a scanned/image-only PDF?"
        )
    return pages


def chunk_documents(
    documents: list[Document], config: Config | None = None
) -> list[Document]:
    """Split page documents into overlapping chunks.

    Uses ``RecursiveCharacterTextSplitter`` with sizes tuned for German prose
    (longer sentences and compound words than typical English defaults). Chunk
    metadata inherits ``source`` and ``page`` from the parent page.

    Args:
        documents: Page-level documents, e.g. from :func:`load_pdf`.
        config: Configuration; falls back to :func:`get_config`.

    Returns:
        Chunk-level documents.
    """
    cfg = config or get_config()
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=cfg.chunk_size,
        chunk_overlap=cfg.chunk_overlap,
        length_function=len,
        # Prefer paragraph, then line, then sentence-ish, then word boundaries.
        separators=["\n\n", "\n", ". ", "? ", "! ", " ", ""],
    )
    return splitter.split_documents(documents)


@dataclass(frozen=True)
class ChunkStats:
    """Summary statistics over a set of chunks."""

    num_chunks: int
    total_chars: int
    min_chars: int
    max_chars: int
    avg_chars: float


def chunk_stats(chunks: list[Document]) -> ChunkStats:
    """Compute size statistics over ``chunks``.

    Args:
        chunks: Chunk-level documents.

    Returns:
        A :class:`ChunkStats` summary (all-zero if ``chunks`` is empty).
    """
    if not chunks:
        return ChunkStats(0, 0, 0, 0, 0.0)
    lengths = [len(c.page_content) for c in chunks]
    total = sum(lengths)
    return ChunkStats(
        num_chunks=len(chunks),
        total_chars=total,
        min_chars=min(lengths),
        max_chars=max(lengths),
        avg_chars=round(total / len(chunks), 1),
    )


def ingest(path: str | Path, config: Config | None = None) -> list[Document]:
    """Load and chunk a PDF in one call.

    Args:
        path: Path to the PDF file.
        config: Configuration; falls back to :func:`get_config`.

    Returns:
        Chunk-level documents ready for embedding.
    """
    cfg = config or get_config()
    return chunk_documents(load_pdf(path), cfg)


def _main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m pdfragen.ingestion <path-to-pdf>", file=sys.stderr)
        return 2

    cfg = get_config()
    pages = load_pdf(argv[0])
    chunks = chunk_documents(pages, cfg)
    stats = chunk_stats(chunks)

    print(f"File:        {argv[0]}")
    print(f"Pages:       {len(pages)}")
    print(f"Chunk size:  {cfg.chunk_size} (overlap {cfg.chunk_overlap})")
    print(f"Chunks:      {stats.num_chunks}")
    print(f"Total chars: {stats.total_chars}")
    print(f"Chars/chunk: min {stats.min_chars}, avg {stats.avg_chars}, max {stats.max_chars}")
    if chunks:
        preview = chunks[0].page_content[:200].replace("\n", " ")
        print(f"\nFirst chunk (page {chunks[0].metadata.get('page')}):\n{preview}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
