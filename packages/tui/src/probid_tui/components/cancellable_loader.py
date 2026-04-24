"""Loader with escape-triggered cancellation."""

from __future__ import annotations

from collections.abc import Callable

from probid_tui.components.loader import Loader
from probid_tui.core.keys import parse_key


class CancellableLoader(Loader):
    def __init__(
        self,
        spinner_style: Callable[[str], str] | None = None,
        message_style: Callable[[str], str] | None = None,
        message: str = "Loading...",
    ):
        super().__init__(spinner_style, message_style, message)
        self.aborted = False
        self.on_abort: Callable[[], None] | None = None
        self.signal = self  # lightweight compatibility handle

    def handle_input(self, data: bytes) -> bool:
        key = parse_key(data)
        if key in {"escape", "ctrl+c"}:
            self.aborted = True
            if self.on_abort is not None:
                self.on_abort()
            return True
        return False
