"""Tests for the retrieval metrics and confidence intervals."""

from __future__ import annotations

import pytest

from pdfragen.evaluation.metrics import (
    bootstrap_ci,
    dedupe_ranked,
    first_hit_rank,
    hit_at_k,
    mean_reciprocal_rank,
    paired_bootstrap_diff,
    recall_at_k,
    reciprocal_rank,
    wilson_ci,
)


def test_first_hit_rank_is_one_indexed() -> None:
    assert first_hit_rank([True, False]) == 1
    assert first_hit_rank([False, False, True]) == 3


def test_first_hit_rank_none_when_no_hit() -> None:
    assert first_hit_rank([False, False]) is None
    assert first_hit_rank([]) is None


def test_dedupe_ranked_keeps_first_occurrence_order() -> None:
    assert dedupe_ranked([("a", 1), ("a", 1), ("b", 0), ("a", 1), ("a", 0)]) == [
        ("a", 1),
        ("b", 0),
        ("a", 0),
    ]


def test_hit_at_k_boundaries() -> None:
    assert hit_at_k(3, 3) == 1.0
    assert hit_at_k(4, 3) == 0.0
    assert hit_at_k(None, 5) == 0.0
    with pytest.raises(ValueError):
        hit_at_k(1, 0)


def test_reciprocal_rank() -> None:
    assert reciprocal_rank(1) == 1.0
    assert reciprocal_rank(4) == 0.25
    assert reciprocal_rank(None) == 0.0


def test_recall_at_k_known_values() -> None:
    ranks = [1, 2, None, 5]
    assert recall_at_k(ranks, 1) == 0.25
    assert recall_at_k(ranks, 3) == 0.5
    assert recall_at_k(ranks, 5) == 0.75


def test_recall_is_monotonic_in_k() -> None:
    ranks = [1, 3, 2, None, 7, 4]
    values = [recall_at_k(ranks, k) for k in range(1, 10)]
    assert values == sorted(values)


def test_mrr_known_value() -> None:
    # (1 + 1/2 + 0 + 1/4) / 4
    assert mean_reciprocal_rank([1, 2, None, 4]) == pytest.approx(0.4375)


def test_metrics_reject_empty_input() -> None:
    with pytest.raises(ValueError):
        recall_at_k([], 1)
    with pytest.raises(ValueError):
        mean_reciprocal_rank([])


def test_bootstrap_ci_contains_mean_and_is_reproducible() -> None:
    values = [1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0, 0.0, 1.0, 1.0]
    low, high = bootstrap_ci(values, seed=1)
    assert 0.0 <= low <= 0.7 <= high <= 1.0
    assert bootstrap_ci(values, seed=1) == (low, high)


def test_bootstrap_ci_degenerate_when_constant() -> None:
    assert bootstrap_ci([1.0] * 8) == (1.0, 1.0)


def test_paired_bootstrap_diff() -> None:
    mean, low, high = paired_bootstrap_diff([1.0, 1.0, 1.0, 0.0], [0.0, 1.0, 0.0, 0.0])
    assert mean == pytest.approx(0.5)
    assert low <= mean <= high
    with pytest.raises(ValueError):
        paired_bootstrap_diff([1.0], [1.0, 0.0])


def test_wilson_ci_known_value() -> None:
    # 8/10 at 95%: textbook Wilson interval ≈ (0.490, 0.943)
    low, high = wilson_ci(8, 10)
    assert low == pytest.approx(0.490, abs=1e-3)
    assert high == pytest.approx(0.943, abs=1e-3)


def test_wilson_ci_edges_stay_in_unit_interval() -> None:
    assert wilson_ci(0, 5)[0] == 0.0
    assert wilson_ci(5, 5)[1] == 1.0
    with pytest.raises(ValueError):
        wilson_ci(6, 5)
