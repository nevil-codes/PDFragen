"""Answer-language detection (English vs German) with lingua.

lingua is restricted to the two languages of interest, which makes it far
more reliable on short answers than open-set detectors. Besides an overall
label, a sentence-level German share is reported, because an English answer
that quotes German terms and a code-switched answer look alike as a whole.

Answers about German documents quote German terms ("Verlängerung"), and
lingua's character rules treat a single umlaut as decisive. So text is
normalised first (quoted/parenthesised spans dropped, umlauts transliterated),
and an independent function-word vote is computed; disagreement or low
confidence marks the answer for manual review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from lingua import Language, LanguageDetectorBuilder

_CODES = {Language.ENGLISH: "en", Language.GERMAN: "de"}
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?:])\s+|\n+")
_QUOTED = re.compile(r"\([^)]*\)|\"[^\"]*\"|„[^“”]*[“”]|“[^”]*”|«[^»]*»")
_TRANSLITERATE = str.maketrans(
    {"ä": "ae", "ö": "oe", "ü": "ue", "Ä": "Ae", "Ö": "Oe", "Ü": "Ue", "ß": "ss"}
)
_WORD = re.compile(r"[^\W\d_]+")
# Closed-class words: never quoted as document terms, so they reflect the
# language the answer is actually written in.
_FUNCTION_WORDS = {
    "en": set(
        "the a an and or but of to in on at for with by from is are was were be "
        "been it this that these those you your i we they he she not no yes can "
        "must will would should have has do does if than as".split()
    ),
    "de": set(
        "der die das den dem des ein eine einen einem einer und oder aber von zu "
        "im in am an auf für mit bei aus ist sind war waren sein es dies diese "
        "sie ihr ihre ich wir er nicht kein keine ja nein kann können muss müssen "
        "wird werden sollte haben hat wenn als wie auch noch nur".split()
    ),
}


@dataclass(frozen=True)
class LanguageResult:
    """Detected language of a text."""

    label: str  # "en", "de", or "unknown" (empty / undetectable)
    confidence: float  # lingua confidence for ``label``
    de_share: float  # fraction of characters in sentences detected as German
    function_word_label: str  # "en", "de", or "unknown" (tie / no function words)
    needs_review: bool  # detectors disagree or confidence is low


@lru_cache(maxsize=1)
def _detector():
    return (
        LanguageDetectorBuilder.from_languages(*_CODES)
        .with_preloaded_language_models()
        .build()
    )


def _normalise(text: str) -> str:
    return _QUOTED.sub(" ", text).translate(_TRANSLITERATE)


def function_word_vote(text: str) -> str:
    """Label ``text`` by counting English vs German function words."""
    words = [w.lower() for w in _WORD.findall(text)]
    en = sum(w in _FUNCTION_WORDS["en"] for w in words)
    de = sum(w in _FUNCTION_WORDS["de"] for w in words)
    if en == de:
        return "unknown"
    return "en" if en > de else "de"


def detect_language(text: str, review_below: float = 0.8) -> LanguageResult:
    """Classify ``text`` as English or German.

    Args:
        text: Model answer.
        review_below: lingua confidence under which ``needs_review`` is set.

    Returns:
        A :class:`LanguageResult`; ``label`` is ``"unknown"`` for empty input.
    """
    normalised = _normalise(text)
    if not _WORD.search(normalised):
        return LanguageResult("unknown", 0.0, 0.0, "unknown", bool(text.strip()))
    detector = _detector()
    top = detector.compute_language_confidence_values(normalised)[0]
    label = _CODES[top.language]

    de_chars = total_chars = 0
    for sentence in filter(None, (s.strip() for s in _SENTENCE_SPLIT.split(normalised))):
        if not _WORD.search(sentence):
            continue
        total_chars += len(sentence)
        if detector.detect_language_of(sentence) == Language.GERMAN:
            de_chars += len(sentence)

    vote = function_word_vote(text)
    return LanguageResult(
        label=label,
        confidence=round(top.value, 4),
        de_share=round(de_chars / total_chars, 4) if total_chars else 0.0,
        function_word_label=vote,
        needs_review=top.value < review_below or vote not in ("unknown", label),
    )
