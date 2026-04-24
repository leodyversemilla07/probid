"""Spinner loader component."""

from __future__ import annotations

import time
from collections.abc import Callable

from probid_tui.components.text import Text


class Loader(Text):
    _frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

    def __init__(
        self,
        spinner_style: Callable[[str], str] | None = None,
        message_style: Callable[[str], str] | None = None,
        message: str = "Loading...",
    ):
        super().__init__("")
        self.spinner_style = spinner_style or (lambda s: s)
        self.message_style = message_style or (lambda s: s)
        self.message = message
        self._running = False
        self._started_at = time.monotonic()

    def start(self) -> None:
        self._running = True
        self._started_at = time.monotonic()

    def stop(self) -> None:
        self._running = False

    def set_message(self, message: str) -> None:
        self.message = message

    def render(self, width: int) -> list[str]:
        if not self._running:
            return []
        idx = int((time.monotonic() - self._started_at) * 10) % len(self._frames)
        spinner = self.spinner_style(self._frames[idx])
        body = self.message_style(self.message)
        self.set_text(f"{spinner} {body}")
        return super().render(width)
