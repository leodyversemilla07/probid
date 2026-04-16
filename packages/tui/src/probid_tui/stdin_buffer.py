"""Buffered stdin splitter with paste event support."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Literal, TypedDict

from probid_tui.core.keys import split_input_sequences


@dataclass(frozen=True)
class StdinBufferOptions:
    timeout: int = 10


class StdinBufferEventMap(TypedDict, total=False):
    data: str
    paste: str


EventName = Literal["data", "paste"]


class StdinBuffer:
    def __init__(self, options: StdinBufferOptions | None = None):
        self.options = options or StdinBufferOptions()
        self._listeners: dict[str, list[Callable[[str], None]]] = {"data": [], "paste": []}
        self._buffer = b""

    def on(self, event: EventName, listener: Callable[[str], None]) -> None:
        self._listeners[event].append(listener)

    def off(self, event: EventName, listener: Callable[[str], None]) -> None:
        if listener in self._listeners[event]:
            self._listeners[event].remove(listener)

    def _emit(self, event: EventName, payload: str) -> None:
        for listener in list(self._listeners[event]):
            listener(payload)

    def process(self, data: bytes | str) -> None:
        incoming = data.encode("utf-8", errors="replace") if isinstance(data, str) else data
        self._buffer += incoming

        # Emit fully enclosed bracketed paste blocks first.
        while True:
            start = self._buffer.find(b"\x1b[200~")
            if start < 0:
                break
            end = self._buffer.find(b"\x1b[201~", start + 6)
            if end < 0:
                # Wait for more bytes.
                break
            payload = self._buffer[start + 6 : end].decode("utf-8", errors="replace")
            self._emit("paste", payload)
            self._buffer = self._buffer[:start] + self._buffer[end + 6 :]

        # Split remaining raw bytes as key/data chunks.
        if self._buffer:
            for chunk in split_input_sequences(self._buffer):
                self._emit("data", chunk.decode("utf-8", errors="replace"))
            self._buffer = b""

    def destroy(self) -> None:
        self._listeners = {"data": [], "paste": []}
        self._buffer = b""

