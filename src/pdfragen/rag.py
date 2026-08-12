"""Retrieval + generation.

Retrieves relevant chunks for a question (English or German — the multilingual
embedding model handles cross-lingual matching), builds a grounded prompt, and
calls a local Ollama model for the answer. Run end-to-end against an already
-ingested PDF:

    python -m pdfragen.rag "What is the deadline mentioned in the letter?"
"""

from __future__ import annotations

import sys
from dataclasses import dataclass

from langchain_core.documents import Document
from langchain_ollama import ChatOllama

from pdfragen.config import Config, get_config
from pdfragen.vectorstore import get_vectorstore

_SYSTEM_PROMPT = """You are a helpful assistant answering questions about a document \
for an international student in Germany. Answer in the same language as the \
question (English or German). Base your answer only on the provided excerpts; \
if the excerpts don't contain the answer, say so plainly instead of guessing."""

_PROMPT_TEMPLATE = """Document excerpts:
{context}

Question: {question}

Answer:"""


@dataclass(frozen=True)
class Source:
    """A retrieved chunk cited in an answer."""

    page: int | str
    text: str


@dataclass(frozen=True)
class Answer:
    """A generated answer with the sources it was grounded in."""

    text: str
    sources: list[Source]


def retrieve(
    question: str, config: Config | None = None, vectorstore=None
) -> list[Document]:
    """Fetch the top-k chunks most relevant to ``question``.

    Args:
        question: User question, in English or German.
        config: Configuration; falls back to :func:`get_config`.
        vectorstore: Store to search; falls back to :func:`get_vectorstore`.

    Returns:
        The top ``config.top_k`` matching chunks.
    """
    cfg = config or get_config()
    store = vectorstore or get_vectorstore(cfg)
    return store.similarity_search(question, k=cfg.top_k)


def _build_prompt(question: str, chunks: list[Document]) -> str:
    context = "\n\n".join(
        f"[page {c.metadata.get('page', '?')}] {c.page_content}" for c in chunks
    )
    return _PROMPT_TEMPLATE.format(context=context, question=question)


def _get_llm(config: Config | None = None) -> ChatOllama:
    cfg = config or get_config()
    return ChatOllama(model=cfg.llm_model, base_url=cfg.ollama_base_url)


def answer(
    question: str,
    config: Config | None = None,
    vectorstore=None,
    llm: ChatOllama | None = None,
    language: str | None = None,
) -> Answer:
    """Answer ``question`` by retrieving context and calling the local LLM.

    Args:
        question: User question, in English or German.
        config: Configuration; falls back to :func:`get_config`.
        vectorstore: Store to search; falls back to :func:`get_vectorstore`.
        llm: Chat model to call; falls back to a configured :class:`ChatOllama`.
        language: If set (e.g. ``"English"``, ``"Deutsch"``), forces the
            answer language instead of matching the question's language.

    Returns:
        The generated answer along with the chunks it cites as sources.

    Raises:
        ConnectionError: If Ollama isn't reachable at the configured base URL.
    """
    cfg = config or get_config()
    chunks = retrieve(question, cfg, vectorstore)

    if not chunks:
        return Answer(
            text="I couldn't find anything relevant in the document for that question.",
            sources=[],
        )

    model = llm or _get_llm(cfg)
    prompt = _build_prompt(question, chunks)
    system_prompt = _SYSTEM_PROMPT
    if language:
        system_prompt += f" Always answer in {language}, regardless of the question's language."

    try:
        response = model.invoke(
            [
                ("system", system_prompt),
                ("human", prompt),
            ]
        )
    except Exception as exc:
        raise ConnectionError(
            f"Could not reach Ollama at {cfg.ollama_base_url}. "
            f"Is `ollama serve` running and is '{cfg.llm_model}' pulled? "
            f"(`ollama pull {cfg.llm_model}`)"
        ) from exc

    sources = [
        Source(page=c.metadata.get("page", "?"), text=c.page_content) for c in chunks
    ]
    return Answer(text=response.content, sources=sources)


def _main(argv: list[str]) -> int:
    if len(argv) != 1:
        print('usage: python -m pdfragen.rag "<question>"', file=sys.stderr)
        return 2

    result = answer(argv[0])
    print(f"Answer:\n{result.text}\n")
    if result.sources:
        print("Sources:")
        for src in result.sources:
            preview = src.text[:150].replace("\n", " ")
            print(f"  [page {src.page}] {preview}...")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
