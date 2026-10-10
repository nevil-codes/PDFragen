"""Benchmark format: one JSON object per line.

Fields:
    id               Unique question id, e.g. ``"abh-01"``.
    doc_file         PDF file name, resolved against the benchmark's docs dir.
    gold_page        1-indexed page that answers the question (as shown in a
                     PDF viewer; pipeline metadata is 0-indexed).
    question_en      The question in English.
    question_de      The same question in German.
    reference_answer Short reference answer (English), for hand-checking.
    gold_evidence    Optional verbatim German span from ``gold_page`` that
                     answers the question. Enables chunk-level scoring, which
                     matters for short documents where page-level recall
                     saturates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

LANGUAGES = ("en", "de")

_REQUIRED = ("id", "doc_file", "gold_page", "question_en", "question_de", "reference_answer")


@dataclass(frozen=True)
class BenchmarkItem:
    """One benchmark question with its gold location."""

    id: str
    doc_file: str
    gold_page: int
    question_en: str
    question_de: str
    reference_answer: str
    gold_evidence: str | None = None

    def question(self, language: str) -> str:
        """Return the question text in ``language`` (``"en"`` or ``"de"``)."""
        if language not in LANGUAGES:
            raise ValueError(f"Unknown language {language!r}; expected one of {LANGUAGES}")
        return self.question_en if language == "en" else self.question_de


def normalize_text(text: str) -> str:
    """Collapse all whitespace runs to single spaces (PDF line breaks vary)."""
    return " ".join(text.split())


def load_benchmark(paths: list[str | Path]) -> list[BenchmarkItem]:
    """Load and validate benchmark items from one or more JSONL files.

    Args:
        paths: JSONL files to read, in order.

    Returns:
        All items, in file order.

    Raises:
        ValueError: On a missing field, bad page number, or duplicate id.
    """
    items: list[BenchmarkItem] = []
    seen: set[str] = set()
    for path in paths:
        for lineno, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
            if not line.strip():
                continue
            where = f"{path}:{lineno}"
            record = json.loads(line)
            missing = [k for k in _REQUIRED if record.get(k) in (None, "")]
            if missing:
                raise ValueError(f"{where}: missing field(s) {missing}")
            if not isinstance(record["gold_page"], int) or record["gold_page"] < 1:
                raise ValueError(f"{where}: gold_page must be a 1-indexed int")
            if record["id"] in seen:
                raise ValueError(f"{where}: duplicate id {record['id']!r}")
            seen.add(record["id"])
            items.append(
                BenchmarkItem(**{k: record.get(k) for k in BenchmarkItem.__dataclass_fields__})
            )
    return items
