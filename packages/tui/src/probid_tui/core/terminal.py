"""Terminal abstraction and process terminal implementation."""

from __future__ import annotations

import os
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable

# Platform-specific imports - handle missing modules gracefully
_has_signal = False
_has_termios = False
_has_tty = False
_has_fcntl = False

if sys.platform != "win32":
    try:
        import fcntl  # noqa: F401
        import signal
        import termios
        import tty  # noqa: F401

        _has_signal = hasattr(signal, "SIGWINCH")
        _has_termios = True
        _has_tty = True
        _has_fcntl = True
    except (ImportError, AttributeError):
        pass

_SIGWINCH = getattr(signal, "SIGWINCH", None) if _has_signal else None
_TIOCGWINSZ = getattr(termios, "TIOCGWINSZ", None) if _has_termios else None
_TCSADRAIN = getattr(termios, "TCSADRAIN", None) if _has_termios else None


class Terminal(ABC):
    @abstractmethod
    def start(
        self,
        on_input: Callable[[bytes], None] | None = None,
        on_resize: Callable[[], None] | None = None,
    ) -> None: ...

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

        if _SIGWINCH is not None:
            signal.signal(_SIGWINCH, self._handle_resize)
        self._enter_raw_mode()
        self._enable_kitty_protocol()
        self._enable_bracketed_paste()
        self.hide_cursor()

    @property
    def kitty_protocol_active(self) -> bool:
        return self._kitty_protocol_active

    def start(
        self,
        on_input: Callable[[bytes], None] | None = None,
        on_resize: Callable[[], None] | None = None,
    ) -> None:
        self._input_callback = on_input
        if on_resize is not None:
            self.on_resize(lambda _c, _r: on_resize())

    def stop(self) -> None:
        self.restore()

    async def drain_input(self, max_ms: int = 1000, idle_ms: int = 50) -> None:
        _ = (max_ms, idle_ms)
        return

    def _enter_raw_mode(self) -> None:
        if _has_termios and _has_tty:
            try:
                import termios
                import tty

                self._old_settings = termios.tcgetattr(self._fd)
                tty.setraw(self._fd)
            except Exception:
                self._old_settings = None
        else:
            self._old_settings = None

    def restore(self) -> None:
        if self._old_settings is not None and _has_termios:
            try:
                import termios

                if _TCSADRAIN is not None:
                    termios.tcsetattr(self._fd, _TCSADRAIN, self._old_settings)
            except Exception:
                pass
        self.show_cursor()
        self._disable_kitty_protocol()
        self._disable_bracketed_paste()

    def write(self, data: str) -> None:
        sys.stdout.write(data)
        sys.stdout.flush()

    def get_size(self) -> tuple[int, int]:
        if _has_fcntl and _has_termios and _TIOCGWINSZ is not None:
            try:
                import fcntl
                import struct

                buf = fcntl.ioctl(self._fd, _TIOCGWINSZ, b"\x00" * 8)
                rows, cols = struct.unpack("HHHH", buf)[:2]
                return cols, rows
            except Exception:
                pass
        # Fallback to environment variables
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
