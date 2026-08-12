"""Central configuration, loaded from environment (.env) with sane defaults.

Keeping every tunable (model names, chunk sizes, paths) here means no value is
hardcoded across the pipeline — callers import `get_config()` and read fields.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Config:
    """Runtime configuration for the RAG pipeline."""

    # LLM (generation, local via Ollama)
    ollama_base_url: str
    llm_model: str

    # Embeddings (local)
    embedding_model: str

    # Chunking
    chunk_size: int
    chunk_overlap: int

    # Retrieval
    top_k: int

    # Storage
    chroma_dir: str
    collection_name: str


def get_config() -> Config:
    """Build a :class:`Config` from environment variables and defaults.

    Returns:
        A frozen ``Config`` snapshot for the current process.
    """
    return Config(
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),
        llm_model=os.getenv("LLM_MODEL", "llama3.1:8b"),
        embedding_model=os.getenv(
            "EMBEDDING_MODEL", "paraphrase-multilingual-MiniLM-L12-v2"
        ),
        chunk_size=int(os.getenv("CHUNK_SIZE", "1000")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "200")),
        top_k=int(os.getenv("TOP_K", "4")),
        chroma_dir=os.getenv("CHROMA_DIR", "chroma_db"),
        collection_name=os.getenv("COLLECTION_NAME", "pdfragen"),
    )
