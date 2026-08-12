"""Embedding and vector storage.

Embeds chunks with a local multilingual sentence-transformers model and
stores them in a persistent local ChromaDB collection. Run end-to-end (load,
chunk, embed, store) to inspect what lands in the collection:

    python -m pdfragen.vectorstore examples/sample.pdf
"""

from __future__ import annotations

import hashlib
import sys

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_huggingface import HuggingFaceEmbeddings

from pdfragen.config import Config, get_config
from pdfragen.ingestion import ingest


def get_embeddings(config: Config | None = None) -> HuggingFaceEmbeddings:
    """Build the local multilingual embedding function.

    Args:
        config: Configuration; falls back to :func:`get_config`.

    Returns:
        A ``HuggingFaceEmbeddings`` wrapper around the configured
        sentence-transformers model, downloaded/cached on first use.
    """
    cfg = config or get_config()
    return HuggingFaceEmbeddings(model_name=cfg.embedding_model)


def get_vectorstore(
    config: Config | None = None,
    embeddings: HuggingFaceEmbeddings | None = None,
) -> Chroma:
    """Open (or create) the persistent local Chroma collection.

    Args:
        config: Configuration; falls back to :func:`get_config`.
        embeddings: Embedding function; falls back to :func:`get_embeddings`.

    Returns:
        A ``Chroma`` vector store backed by ``config.chroma_dir`` on disk.
    """
    cfg = config or get_config()
    return Chroma(
        collection_name=cfg.collection_name,
        embedding_function=embeddings or get_embeddings(cfg),
        persist_directory=cfg.chroma_dir,
    )


def _chunk_id(chunk: Document) -> str:
    """Derive a stable id from source path, page, and content hash.

    Re-ingesting the same PDF overwrites its existing chunks (same ids)
    instead of duplicating them in the collection.
    """
    source = chunk.metadata.get("source", "")
    page = chunk.metadata.get("page", "")
    digest = hashlib.sha1(chunk.page_content.encode("utf-8")).hexdigest()[:8]
    return f"{source}:{page}:{digest}"


def add_chunks(
    chunks: list[Document],
    config: Config | None = None,
    vectorstore: Chroma | None = None,
) -> list[str]:
    """Embed ``chunks`` and upsert them into the vector store.

    Args:
        chunks: Chunk-level documents, e.g. from :func:`pdfragen.ingestion.ingest`.
        config: Configuration; falls back to :func:`get_config`.
        vectorstore: Target store; falls back to :func:`get_vectorstore`.

    Returns:
        The ids assigned to the stored chunks.
    """
    cfg = config or get_config()
    store = vectorstore or get_vectorstore(cfg)
    if not chunks:
        return []
    ids = [_chunk_id(chunk) for chunk in chunks]
    store.add_documents(chunks, ids=ids)
    return ids


def _main(argv: list[str]) -> int:
    if len(argv) != 1:
        print("usage: python -m pdfragen.vectorstore <path-to-pdf>", file=sys.stderr)
        return 2

    cfg = get_config()
    chunks = ingest(argv[0], cfg)
    store = get_vectorstore(cfg)
    ids = add_chunks(chunks, cfg, store)

    print(f"File:       {argv[0]}")
    print(f"Chunks:     {len(chunks)}")
    print(f"Stored as:  {len(ids)} vectors")
    print(f"Collection: {cfg.collection_name} ({store._collection.count()} total)")
    print(f"Persisted:  {cfg.chroma_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
