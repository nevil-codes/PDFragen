"""Query-translation baseline: translate an English question to German with
the local LLM before retrieval, so it can be matched monolingually."""

from __future__ import annotations

from langchain_ollama import ChatOllama

_TRANSLATE_SYSTEM = (
    "You translate questions from English into German. Output only the German "
    "translation of the question, with no quotes, explanations or alternatives."
)


def build_translator(
    model: str, base_url: str, temperature: float = 0.0, seed: int | None = 42
) -> ChatOllama:
    """Build a deterministic-as-possible Ollama chat model for translation."""
    return ChatOllama(model=model, base_url=base_url, temperature=temperature, seed=seed)


def translate_to_german(question: str, llm: ChatOllama) -> str:
    """Translate ``question`` to German, returning a single cleaned line."""
    response = llm.invoke([("system", _TRANSLATE_SYSTEM), ("human", question)])
    text = response.content.strip()
    # Small models sometimes wrap the output in quotes or add a second line.
    first_line = text.splitlines()[0] if text else ""
    return first_line.strip().strip('"„“”«»').strip()
