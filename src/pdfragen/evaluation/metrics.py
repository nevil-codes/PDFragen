"""Retrieval metrics and confidence intervals.

Ranks are 1-indexed; ``None`` means the gold item was not retrieved at all
(within the retrieved depth). Per-query values are kept separate from the
aggregates so the scripts can bootstrap over questions.
"""

from __future__ import annotations

import math
import random
from collections.abc import Callable, Hashable, Sequence


def first_hit_rank(hits: Sequence[bool]) -> int | None:
    """Return the 1-indexed position of the first ``True`` in ``hits``.

    Args:
        hits: Relevance flags for a ranked list, best first.

    Returns:
        The rank of the first relevant item, or ``None`` if there is none.
    """
    for position, hit in enumerate(hits, 1):
        if hit:
            return position
    return None


def dedupe_ranked(keys: Sequence[Hashable]) -> list[Hashable]:
    """Keep the first occurrence of each key, preserving rank order.

    Used for page-level scoring: several chunks from the same page collapse
    into one ranked page, so Recall@k counts the top-k distinct pages.
    """
    seen: set[Hashable] = set()
    unique = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            unique.append(key)
    return unique


def hit_at_k(rank: int | None, k: int) -> float:
    """1.0 if the first relevant item is within the top ``k``, else 0.0."""
    if k < 1:
        raise ValueError(f"k must be >= 1, got {k}")
    return 1.0 if rank is not None and rank <= k else 0.0


def reciprocal_rank(rank: int | None) -> float:
    """``1 / rank``, or 0.0 if nothing relevant was retrieved."""
    return 0.0 if rank is None else 1.0 / rank


def recall_at_k(ranks: Sequence[int | None], k: int) -> float:
    """Mean :func:`hit_at_k` over queries (single gold item per query)."""
    if not ranks:
        raise ValueError("recall_at_k needs at least one query")
    return sum(hit_at_k(r, k) for r in ranks) / len(ranks)


def mean_reciprocal_rank(ranks: Sequence[int | None]) -> float:
    """Mean :func:`reciprocal_rank` over queries."""
    if not ranks:
        raise ValueError("mean_reciprocal_rank needs at least one query")
    return sum(reciprocal_rank(r) for r in ranks) / len(ranks)


def _mean(values: Sequence[float]) -> float:
    return sum(values) / len(values)


def bootstrap_ci(
    values: Sequence[float],
    statistic: Callable[[Sequence[float]], float] = _mean,
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
) -> tuple[float, float]:
    """Percentile bootstrap confidence interval over queries.

    Args:
        values: Per-query values (e.g. hit@k flags or reciprocal ranks).
        statistic: Aggregate to compute on each resample; defaults to the mean.
        n_resamples: Number of bootstrap resamples.
        confidence: Two-sided confidence level.
        seed: RNG seed, for reproducible intervals.

    Returns:
        ``(low, high)`` bounds.
    """
    if not values:
        raise ValueError("bootstrap_ci needs at least one value")
    rng = random.Random(seed)
    n = len(values)
    stats = sorted(
        statistic([values[rng.randrange(n)] for _ in range(n)]) for _ in range(n_resamples)
    )
    alpha = (1.0 - confidence) / 2
    low = stats[int(math.floor(alpha * (n_resamples - 1)))]
    high = stats[int(math.ceil((1.0 - alpha) * (n_resamples - 1)))]
    return low, high


def paired_bootstrap_diff(
    a: Sequence[float],
    b: Sequence[float],
    n_resamples: int = 2000,
    confidence: float = 0.95,
    seed: int = 0,
) -> tuple[float, float, float]:
    """Mean difference ``a - b`` over paired queries, with a bootstrap CI.

    Pairs are resampled together, so per-question difficulty cancels out
    (e.g. EN vs DE versions of the same question).

    Returns:
        ``(mean_diff, low, high)``.
    """
    if len(a) != len(b):
        raise ValueError(f"paired samples differ in length: {len(a)} vs {len(b)}")
    diffs = [x - y for x, y in zip(a, b)]
    low, high = bootstrap_ci(diffs, n_resamples=n_resamples, confidence=confidence, seed=seed)
    return _mean(diffs), low, high


def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score interval for a binomial proportion.

    Better behaved than the normal approximation for small ``n`` or
    proportions near 0/1, which is the typical case for answer-language rates.
    """
    if n <= 0:
        raise ValueError("wilson_ci needs n >= 1")
    if not 0 <= successes <= n:
        raise ValueError(f"successes must be in [0, {n}], got {successes}")
    p = successes / n
    denom = 1 + z**2 / n
    centre = (p + z**2 / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2)) / denom
    return max(0.0, centre - half), min(1.0, centre + half)
