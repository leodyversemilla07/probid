"""Terminal abstraction and process terminal implementation."""

from __future__ import annotations

import fcntl
import os
import signal
import struct
import sys
import termios
import tty
from abc import ABC, abstractmethod
from typing import Callable


class Terminal(ABC):
    @abstractmethod
    def start(self, on_input: Callable[[bytes], None] | None = None, on_resize: Callable[[], None] | None = None) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    async def drain_input(self, max_ms: int = 1000, idle_ms: int = 50) -> None: ...

    @abstractmethod
    def write(self, data: str) -> None: ...

    @abstractmethod
    def get_size(self) -> tuple[int, int]: ...  # (cols, rows)

    @abstractmethod
    def on_resize(self, callback: Callable[[int, int], None]) -> None: ...

    def hide_cursor(self) -> None:
        self.write("\x1b[?25l")

    def show_cursor(self) -> None:
        self.write("\x1b[?25h")

    def clear_screen(self) -> None:
        self.write("\x1b[2J\x1b[H")

    def clear_line(self) -> None:
        self.write("\x1b[2K\r")

    def clear_from_cursor(self) -> None:
        self.write("\x1b[J")

    def move_by(self, lines: int) -> None:
        if lines == 0:
            return
        if lines < 0:
            self.write(f"\x1b[{abs(lines)}A")
        else:
            self.write(f"\x1b[{lines}B")

    def set_title(self, title: str) -> None:
        self.write(f"\x1b]0;{title}\x07")


class ProcessTerminal(Terminal):
    """Raw-mode process terminal with resize callbacks.

    Uses unix tty/termios APIs and gracefully no-ops on unsupported environments.
    """

    def __init__(self):
        self._fd = sys.stdin.fileno()
        self._old_settings: list | None = None
        self._resize_callbacks: list[Callable[[int, int], None]] = []
        self._input_callback: Callable[[bytes], None] | None = None
        self._kitty_protocol_active = False

        signal.signal(signal.SIGWINCH, self._handle_resize)
        self._enter_raw_mode()
        self._enable_kitty_protocol()
        self._enable_bracketed_paste()
        self.hide_cursor()

    @property
    def kitty_protocol_active(self) -> bool:
        return self._kitty_protocol_active

    def start(self, on_input: Callable[[bytes], None] | None = None, on_resize: Callable[[], None] | None = None) -> None:
        self._input_callback = on_input
        if on_resize is not None:
            self.on_resize(lambda _c, _r: on_resize())

    def stop(self) -> None:
        self.restore()

    async def drain_input(self, max_ms: int = 1000, idle_ms: int = 50) -> None:
        _ = (max_ms, idle_ms)
        return

    def _enter_raw_mode(self) -> None:
        try:
            self._old_settings = termios.tcgetattr(self._fd)
            tty.setraw(self._fd)
        except Exception:
            self._old_settings = None

    def restore(self) -> None:
        if self._old_settings is not None:
            try:
                termios.tcsetattr(self._fd, termios.TCSADRAIN, self._old_settings)
            except Exception:
                pass
        self.show_cursor()
        self._disable_kitty_protocol()
        self._disable_bracketed_paste()

    def write(self, data: str) -> None:
        sys.stdout.write(data)
        sys.stdout.flush()

    def get_size(self) -> tuple[int, int]:
        try:
            buf = fcntl.ioctl(self._fd, termios.TIOCGWINSZ, b"\x00" * 8)
            rows, cols = struct.unpack("HHHH", buf)[:2]
            return cols, rows
        except Exception:
            cols = int(os.environ.get("COLUMNS", "80"))
            rows = int(os.environ.get("LINES", "24"))
            return cols, rows

    def on_resize(self, callback: Callable[[int, int], None]) -> None:
        self._resize_callbacks.append(callback)

    def _handle_resize(self, *_args) -> None:
        cols, rows = self.get_size()
        for callback in list(self._resize_callbacks):
            callback(cols, rows)

    def _enable_kitty_protocol(self) -> None:
        self.write("\x1b[>1u")
        self._kitty_protocol_active = True

    def _disable_kitty_protocol(self) -> None:
        self.write("\x1b[<u")
        self._kitty_protocol_active = False

    def _enable_bracketed_paste(self) -> None:
        self.write("\x1b[?2004h")

    def _disable_bracketed_paste(self) -> None:
        self.write("\x1b[?2004l")
