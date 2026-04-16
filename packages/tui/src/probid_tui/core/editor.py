"""Multi-line editor component with pi-like rails and scroll indicators."""

from __future__ import annotations

from typing import Callable

from probid_tui.core.ansi_utils import truncate_to_width
from probid_tui.core.component import Component, Focusable
from probid_tui.core.keys import parse_key


class Editor(Component, Focusable):
    """Editable multi-line buffer with render rails and cursor visualization."""

    def __init__(
        self,
        *,
        max_visible_lines: int = 5,
        rail_char: str = "─",
        cursor_char: str = "█",
        history: list[str] | None = None,
        autocomplete: Callable[[str], list[str]] | None = None,
        on_submit: Callable[[str], None] | None = None,
    ):
        self.max_visible_lines = max(1, max_visible_lines)
        self.rail_char = rail_char
        self.cursor_char = cursor_char

        self.focused = False
        self._lines: list[str] = [""]
        self._cursor_row = 0
        self._cursor_col = 0
        self._scroll_offset = 0

        self._history = list(history or [])
        self._history_index: int | None = None
        self._autocomplete = autocomplete
        self._on_submit = on_submit
        self._completions: list[str] = []
        self._completion_index = -1

    # ----------------------- public state helpers -----------------------
    def clear(self) -> None:
        self._lines = [""]
        self._cursor_row = 0
        self._cursor_col = 0
        self._scroll_offset = 0
        self._history_index = None
        self._completions = []
        self._completion_index = -1

    def get_value(self) -> str:
        return "\n".join(self._lines)

    def set_value(self, text: str) -> None:
        parts = text.split("\n")
        self._lines = parts or [""]
        self._cursor_row = len(self._lines) - 1
        self._cursor_col = len(self._lines[self._cursor_row])
        self._history_index = None
        self._refresh_completions()

    def set_on_submit(self, callback: Callable[[str], None] | None) -> None:
        self._on_submit = callback

    def submit(self) -> str:
        value = self.get_value().strip("\n")
        if value and (not self._history or self._history[-1] != value):
            self._history.append(value)
        self.clear()
        return value

    def history_prev(self) -> None:
        if not self._history:
            return
        if self._history_index is None:
            self._history_index = len(self._history) - 1
        else:
            self._history_index = max(0, self._history_index - 1)
        self.set_value(self._history[self._history_index])

    def history_next(self) -> None:
        if not self._history:
            return
        if self._history_index is None:
            return
        self._history_index += 1
        if self._history_index >= len(self._history):
            self._history_index = None
            self.set_value("")
        else:
            self.set_value(self._history[self._history_index])

    # -------------------------- rendering -------------------------------
    def render(self, width: int) -> list[str]:
        width = max(20, width)

        visual_lines, cursor_vrow, cursor_vcol = self._visualize(width)
        self._ensure_cursor_visible(cursor_vrow)

        visible = visual_lines[self._scroll_offset : self._scroll_offset + self.max_visible_lines]
        if not visible:
            visible = ["".ljust(width)]

        lines_above = self._scroll_offset
        lines_below = max(0, len(visual_lines) - (self._scroll_offset + len(visible)))

        top = self._rail(width, "↑", lines_above) if lines_above > 0 else self.rail_char * width
        bottom = self._rail(width, "↓", lines_below) if lines_below > 0 else self.rail_char * width

        # Cursor is already blended into visual lines in _visualize
        body = [truncate_to_width(line, width, pad=True) for line in visible]

        return [top, *body, bottom]

    def _visualize(self, width: int) -> tuple[list[str], int, int]:
        visual_lines: list[str] = []
        cursor_vrow = 0
        cursor_vcol = 0

        current_row_index = 0
        for row, line in enumerate(self._lines):
            chunks = self._wrap_line(line, width)
            if row == self._cursor_row:
                chunk_idx = self._cursor_col // width
                col = self._cursor_col % width
                cursor_vrow = current_row_index + min(chunk_idx, max(0, len(chunks) - 1))
                cursor_vcol = col

            visual_lines.extend(chunks)
            current_row_index += len(chunks)

        if not visual_lines:
            visual_lines = [""]

        if self.focused and 0 <= cursor_vrow < len(visual_lines):
            base = visual_lines[cursor_vrow].ljust(width)
            col = min(max(0, cursor_vcol), max(0, width - 1))
            visual_lines[cursor_vrow] = base[:col] + self.cursor_char + base[col + 1 :]

        return visual_lines, cursor_vrow, cursor_vcol

    def _wrap_line(self, line: str, width: int) -> list[str]:
        if width <= 0:
            return [""]
        if line == "":
            return [""]
        chunks: list[str] = []
        i = 0
        while i < len(line):
            chunks.append(line[i : i + width])
            i += width
        return chunks or [""]

    def _rail(self, width: int, arrow: str, count: int) -> str:
        indicator = f"─── {arrow} {count} more "
        if len(indicator) >= width:
            return indicator[:width]
        return indicator + (self.rail_char * (width - len(indicator)))

    def _ensure_cursor_visible(self, cursor_vrow: int) -> None:
        if cursor_vrow < self._scroll_offset:
            self._scroll_offset = cursor_vrow
        elif cursor_vrow >= self._scroll_offset + self.max_visible_lines:
            self._scroll_offset = cursor_vrow - self.max_visible_lines + 1
        self._scroll_offset = max(0, self._scroll_offset)

    # -------------------------- input ----------------------------------
    def handle_input(self, data: bytes) -> bool:
        # bracketed paste payload: ESC[200~ ... ESC[201~
        if data.startswith(b"\x1b[200~") and data.endswith(b"\x1b[201~"):
            payload = data[len(b"\x1b[200~") : -len(b"\x1b[201~")]
            self._insert_text(payload.decode("utf-8", errors="replace"))
            return True

        key = parse_key(data)
        if key:
            if self._handle_key(key):
                return True

        # printable fallback
        try:
            text = data.decode("utf-8", errors="ignore")
        except Exception:
            return False
        if text and text.isprintable() and text not in {"\x00", "\x1b"}:
            self._insert_text(text)
            return True
        return False

    def _handle_key(self, key: str) -> bool:
        if key in {"left", "ctrl+b"}:
            self._move_left()
            return True
        if key in {"right", "ctrl+f"}:
            self._move_right()
            return True
        if key in {"up"}:
            self._move_up()
            return True
        if key in {"down"}:
            self._move_down()
            return True
        if key in {"home", "ctrl+a"}:
            self._cursor_col = 0
            return True
        if key in {"end", "ctrl+e"}:
            self._cursor_col = len(self._lines[self._cursor_row])
            return True
        if key in {"backspace", "ctrl+h"}:
            self._backspace()
            return True
        if key in {"enter"}:
            if self._on_submit is not None:
                self._on_submit(self.submit())
            else:
                self._newline()
            return True
        if key in {"shift+enter"}:
            self._newline()
            return True
        if key in {"page_up"}:
            self.history_prev()
            return True
        if key in {"page_down"}:
            self.history_next()
            return True
        if key in {"tab"}:
            return self._apply_completion()
        return False

    def _insert_text(self, text: str) -> None:
        for ch in text:
            if ch == "\n":
                self._newline()
            else:
                line = self._lines[self._cursor_row]
                self._lines[self._cursor_row] = line[: self._cursor_col] + ch + line[self._cursor_col :]
                self._cursor_col += 1
        self._refresh_completions()

    def _newline(self) -> None:
        line = self._lines[self._cursor_row]
        before = line[: self._cursor_col]
        after = line[self._cursor_col :]
        self._lines[self._cursor_row] = before
        self._lines.insert(self._cursor_row + 1, after)
        self._cursor_row += 1
        self._cursor_col = 0
        self._refresh_completions()

    def _backspace(self) -> None:
        if self._cursor_col > 0:
            line = self._lines[self._cursor_row]
            self._lines[self._cursor_row] = line[: self._cursor_col - 1] + line[self._cursor_col :]
            self._cursor_col -= 1
        elif self._cursor_row > 0:
            prev = self._lines[self._cursor_row - 1]
            current = self._lines.pop(self._cursor_row)
            self._cursor_row -= 1
            self._cursor_col = len(prev)
            self._lines[self._cursor_row] = prev + current
        self._refresh_completions()

    def _move_left(self) -> None:
        if self._cursor_col > 0:
            self._cursor_col -= 1
        elif self._cursor_row > 0:
            self._cursor_row -= 1
            self._cursor_col = len(self._lines[self._cursor_row])

    def _move_right(self) -> None:
        line_len = len(self._lines[self._cursor_row])
        if self._cursor_col < line_len:
            self._cursor_col += 1
        elif self._cursor_row < len(self._lines) - 1:
            self._cursor_row += 1
            self._cursor_col = 0

    def _move_up(self) -> None:
        if self._cursor_row > 0:
            self._cursor_row -= 1
            self._cursor_col = min(self._cursor_col, len(self._lines[self._cursor_row]))

    def _move_down(self) -> None:
        if self._cursor_row < len(self._lines) - 1:
            self._cursor_row += 1
            self._cursor_col = min(self._cursor_col, len(self._lines[self._cursor_row]))

    def _refresh_completions(self) -> None:
        self._completions = []
        self._completion_index = -1
        if self._autocomplete is None:
            return
        prefix = self._lines[self._cursor_row][: self._cursor_col]
        try:
            self._completions = self._autocomplete(prefix)[:10]
        except Exception:
            self._completions = []

    def _apply_completion(self) -> bool:
        if not self._completions:
            return False
        self._completion_index = (self._completion_index + 1) % len(self._completions)
        completion = self._completions[self._completion_index]
        self._lines[self._cursor_row] = completion
        self._cursor_col = len(completion)
        return True

    def get_cursor_position(self) -> tuple[int, int] | None:
        width = 120
        _visual, row, col = self._visualize(width)
        return row, col
