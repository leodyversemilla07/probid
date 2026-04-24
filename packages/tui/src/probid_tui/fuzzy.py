"""Fuzzy matching helpers (pi-tui compatible surface)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(frozen=True)
class FuzzyMatch:
    query: str
    text: str
    score: float
    indices: list[int]


def fuzzy_match(query: str, text: str) -> FuzzyMatch:
    """Subsequence fuzzy match with simple contiguous/start bonuses."""
    q = (query or "").strip().lower()
    t = text or ""
    tl = t.lower()

    if not q:
        return FuzzyMatch(query=query, text=text, score=1.0, indices=[])

    qi = 0
    indices: list[int] = []
    for ti, ch in enumerate(tl):
        if qi < len(q) and ch == q[qi]:
            indices.append(ti)
            qi += 1
            if qi == len(q):
                break

    if qi != len(q):
        return FuzzyMatch(query=query, text=text, score=0.0, indices=[])

    # Base score: matched length vs text length.
    score = len(q) / max(1, len(t))

    # Contiguous bonus.
    contiguous_pairs = 0
    for i in range(1, len(indices)):
        if indices[i] == indices[i - 1] + 1:
            contiguous_pairs += 1
    score += contiguous_pairs * 0.1

    # Prefix bonus.
    if indices and indices[0] == 0:
        score += 0.2

    # Clamp.
    score = max(0.0, min(1.0, score))
    return FuzzyMatch(query=query, text=text, score=score, indices=indices)


def fuzzy_filter(items: list[T], query: str, get_text: Callable[[T], str]) -> list[T]:
    """Return items matching query, sorted by score desc."""
    matches: list[tuple[float, int, T]] = []
    for idx, item in enumerate(items):
        m = fuzzy_match(query, get_text(item))
        if m.score > 0:
            matches.append((m.score, -idx, item))
    matches.sort(reverse=True)
    return [item for _score, _neg_idx, item in matches]


# pi-tui style aliases
fuzzyMatch = fuzzy_match
fuzzyFilter = fuzzy_filter
