"""Kill ring (Emacs-style clipboard history)."""

from __future__ import annotations


class KillRing:
    def __init__(self, max_items: int = 64):
        self.max_items = max(1, max_items)
        self._items: list[str] = []
        self._index = -1

    @property
    def length(self) -> int:
        return len(self._items)

    def push(self, text: str, *, prepend: bool = False, accumulate: bool = False) -> None:
        if not text:
            return
        if accumulate and self._items:
            if prepend:
                self._items[0] = text + self._items[0]
            else:
                self._items[0] = self._items[0] + text
            self._index = 0
            return

        self._items.insert(0, text)
        if len(self._items) > self.max_items:
            self._items = self._items[: self.max_items]
        self._index = 0

    def peek(self) -> str:
        if not self._items:
            return ""
        if self._index < 0:
            self._index = 0
        return self._items[self._index]

    def yank(self) -> str:
        return self.peek()

    def rotate(self) -> str:
        if not self._items:
            return ""
        if self._index < 0:
            self._index = 0
        self._index = (self._index + 1) % len(self._items)
        return self._items[self._index]

    def clear(self) -> None:
        self._items.clear()
        self._index = -1
