"""Undo/redo stack primitive."""

from __future__ import annotations

from copy import deepcopy
from typing import Generic, TypeVar

S = TypeVar("S")


class UndoStack(Generic[S]):
    def __init__(self, max_items: int = 256):
        self.max_items = max(1, max_items)
        self._past: list[S] = []
        self._future: list[S] = []

    def push(self, state: S) -> None:
        self._past.append(deepcopy(state))
        if len(self._past) > self.max_items:
            self._past = self._past[-self.max_items :]
        self._future.clear()

    def can_undo(self) -> bool:
        return bool(self._past)

    def can_redo(self) -> bool:
        return bool(self._future)

    def undo(self, current_state: S) -> S | None:
        if not self._past:
            return None
        prev = self._past.pop()
        self._future.append(deepcopy(current_state))
        return deepcopy(prev)

    def redo(self, current_state: S) -> S | None:
        if not self._future:
            return None
        nxt = self._future.pop()
        self._past.append(deepcopy(current_state))
        return deepcopy(nxt)

    def clear(self) -> None:
        self._past.clear()
        self._future.clear()
