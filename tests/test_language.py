"""Sanity checks for the EN/DE answer-language detector."""

from __future__ import annotations

import pytest

pytest.importorskip("lingua")

from pdfragen.evaluation.language import detect_language  # noqa: E402


def test_detects_english_answer_quoting_german_terms() -> None:
    result = detect_language(
        "You must apply for the extension (Verlängerung) by 5 September 2026 "
        "and bring your rental contract (Mietvertrag)."
    )
    assert result.label == "en"
    assert result.de_share == 0.0


def test_flags_english_answer_dominated_by_german_compounds() -> None:
    # lingua alone calls this German; the function-word vote disagrees.
    result = detect_language(
        "You need to go to the Ausländerbehörde and pay the Bearbeitungsgebühr of 96 euros."
    )
    assert result.function_word_label == "en"
    assert result.label == "en" or result.needs_review


def test_detects_german_answer() -> None:
    result = detect_language(
        "Sie müssen die Verlängerung spätestens bis zum 5. September 2026 beantragen."
    )
    assert result.label == "de"
    assert result.de_share == 1.0
    assert not result.needs_review


def test_code_switched_answer_has_partial_german_share() -> None:
    result = detect_language(
        "The fee is 96 euros. Die Gebühr ist bei der Antragstellung zu entrichten."
    )
    assert 0.0 < result.de_share < 1.0


def test_empty_answer_is_unknown() -> None:
    assert detect_language("   ").label == "unknown"
