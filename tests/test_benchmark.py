"""Integrity checks for the committed evaluation benchmark.

Every gold annotation is verified against the real PDF text, so a typo in a
gold page or evidence span fails CI instead of silently corrupting metrics.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pdfragen.evaluation.benchmark import load_benchmark, normalize_text
from pdfragen.ingestion import load_pdf

ROOT = Path(__file__).resolve().parent.parent
BENCHMARK_FILES = sorted((ROOT / "eval" / "benchmark").glob("*.jsonl"))
DOCS_DIR = ROOT / "examples"
ITEMS = load_benchmark(BENCHMARK_FILES)


def test_benchmark_files_exist() -> None:
    assert BENCHMARK_FILES
    assert len(ITEMS) >= 20


@pytest.mark.parametrize("item", ITEMS, ids=[i.id for i in ITEMS])
def test_gold_evidence_is_on_gold_page(item) -> None:
    pages = load_pdf(DOCS_DIR / item.doc_file)
    assert item.gold_page <= len(pages)
    assert item.gold_evidence, "seed benchmark items should all carry gold_evidence"
    page_text = normalize_text(pages[item.gold_page - 1].page_content)
    assert normalize_text(item.gold_evidence) in page_text


def test_load_benchmark_rejects_duplicate_ids(tmp_path: Path) -> None:
    record = {
        "id": "x-01",
        "doc_file": "a.pdf",
        "gold_page": 1,
        "question_en": "q",
        "question_de": "f",
        "reference_answer": "a",
    }
    path = tmp_path / "dup.jsonl"
    path.write_text("\n".join([json.dumps(record)] * 2))
    with pytest.raises(ValueError, match="duplicate id"):
        load_benchmark([path])


def test_load_benchmark_rejects_zero_indexed_page(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(
        json.dumps(
            {
                "id": "x-01",
                "doc_file": "a.pdf",
                "gold_page": 0,
                "question_en": "q",
                "question_de": "f",
                "reference_answer": "a",
            }
        )
    )
    with pytest.raises(ValueError, match="1-indexed"):
        load_benchmark([path])
