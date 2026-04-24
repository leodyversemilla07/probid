"""Single-line input component."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from probid_tui.core.ansi_utils import visible_width
from probid_tui.core.component import Component, Focusable
from probid_tui.core.keys import parse_key
from probid_tui.kill_ring import KillRing
from probid_tui.undo_stack import UndoStack


@dataclass(frozen=True)
class InputState:
    value: str
    cursor: int


def _is_control(ch: str) -> bool:
    code = ord(ch)
    return code < 32 or code == 0x7F or (0x80 <= code <= 0x9F)


def _is_punctuation(ch: str) -> bool:
    return bool(ch) and (not ch.isalnum()) and (not ch.isspace())


class Input(Component, Focusable):
    def __init__(self):
        self.focused = False
        self._value = ""
        self._cursor = 0
        self.on_submit: Callable[[str], None] | None = None
        self.on_escape: Callable[[], None] | None = None

        self._is_in_paste = False
        self._paste_buffer = ""

        self._kill_ring = KillRing()
        self._last_action: str | None = None  # kill | yank | type-word | None
        self._last_yank_span: tuple[int, int] | None = None
        self._undo_stack = UndoStack[InputState]()

    # ------------------------------------------------------------------ public
    def get_value(self) -> str:
        return self._value

    def set_value(self, value: str) -> None:
        self._value = value
        self._cursor = min(self._cursor, len(self._value))
        self._last_action = None
        self._last_yank_span = None

    # pi-style aliases
    getValue = get_value
    setValue = set_value

    def render(self, width: int) -> list[str]:
        prompt = "> "
        width = max(1, width)
        available = width - visible_width(prompt)
        if available <= 0:
            return [prompt[:width]]

        total_width = visible_width(self._value)
        cursor_col = self._column_of_index(self._cursor)
        if total_width < available:
            visible_text = self._value
            before_cursor = self._value[: self._cursor]
        else:
            scroll_width = max(1, available - 1 if self._cursor >= len(self._value) else available)
            half = scroll_width // 2
            if cursor_col < half:
                start_col = 0
            elif cursor_col > total_width - half:
                start_col = max(0, total_width - scroll_width)
            else:
                start_col = max(0, cursor_col - half)

            visible_text = self._slice_by_columns(self._value, start_col, scroll_width)
            before_cursor = self._slice_by_columns(self._value, start_col, max(0, cursor_col - start_col))

        if self.focused:
            cursor_display = len(before_cursor)
            at_cursor = visible_text[cursor_display : cursor_display + 1] or " "
            after_cursor = visible_text[cursor_display + len(at_cursor) :]
            text = before_cursor + f"\x1b[7m{at_cursor}\x1b[27m" + after_cursor
        else:
            text = visible_text

        line = prompt + text
        pad = " " * max(0, width - visible_width(line))
        return [line + pad]

    def handle_input(self, data: bytes) -> bool:
        text = data.decode("utf-8", errors="replace")
        if "\x1b[200~" in text or self._is_in_paste:
            self._handle_paste_stream(text)
            return True

        key = parse_key(data)
        if key is not None:
            if self._handle_key(key):
                return True

        has_control = any(_is_control(ch) for ch in text)
        if not has_control and text:
            self._insert_text(text)
            return True
        return False

    # pi-style alias
    handleInput = handle_input

    def get_cursor_position(self) -> tuple[int, int] | None:
        return (0, self._cursor)

    # ----------------------------------------------------------------- internals
    def _handle_key(self, key: str) -> bool:
        if key in {"escape", "ctrl+c"}:
            self._last_action = None
            if self.on_escape is not None:
                self.on_escape()
            return True

        if key in {"ctrl+-", "ctrl+_"}:
            self._undo()
            return True

        if key in {"enter"}:
            self._last_action = None
            if self.on_submit is not None:
                self.on_submit(self._value)
            return True

        if key in {"backspace", "ctrl+h"}:
            self._backspace()
            return True
        if key in {"delete", "ctrl+d"}:
            self._forward_delete()
            return True

        if key in {"left", "ctrl+b"}:
            self._move_left()
            return True
        if key in {"right", "ctrl+f"}:
            self._move_right()
            return True
        if key in {"home", "ctrl+a"}:
            self._last_action = None
            self._cursor = 0
            return True
        if key in {"end", "ctrl+e"}:
            self._last_action = None
            self._cursor = len(self._value)
            return True
        if key in {"alt+b"}:
            self._move_word_backwards()
            return True
        if key in {"alt+f"}:
            self._move_word_forwards()
            return True

        if key in {"ctrl+w"}:
            self._delete_word_backwards()
            return True
        if key in {"alt+d"}:
            self._delete_word_forwards()
            return True
        if key in {"ctrl+u"}:
            self._delete_to_line_start()
            return True
        if key in {"ctrl+k"}:
            self._delete_to_line_end()
            return True

        if key in {"ctrl+y"}:
            self._yank()
            return True
        if key in {"alt+y"}:
            self._yank_pop()
            return True

        return False

    def _handle_paste_stream(self, data: str) -> None:
        if "\x1b[200~" in data:
            self._is_in_paste = True
            self._paste_buffer = ""
            data = data.replace("\x1b[200~", "")

        if not self._is_in_paste:
            return

        self._paste_buffer += data
        end = self._paste_buffer.find("\x1b[201~")
        if end < 0:
            return

        content = self._paste_buffer[:end]
        remaining = self._paste_buffer[end + 6 :]
        self._is_in_paste = False
        self._paste_buffer = ""

        self._push_undo()
        clean = content.replace("\r\n", "").replace("\r", "").replace("\n", "").replace("\t", "    ")
        self._value = self._value[: self._cursor] + clean + self._value[self._cursor :]
        self._cursor += len(clean)
        self._last_action = None
        self._last_yank_span = None

        if remaining:
            self.handle_input(remaining.encode("utf-8", errors="replace"))

    def _insert_text(self, text: str) -> None:
        for ch in text:
            if ch in {"\r", "\n"}:
                continue
            self._insert_character(ch)

    def _insert_character(self, ch: str) -> None:
        if ch.isspace() or self._last_action != "type-word":
            self._push_undo()
        self._last_action = "type-word"
        self._last_yank_span = None
        self._value = self._value[: self._cursor] + ch + self._value[self._cursor :]
        self._cursor += len(ch)

    def _backspace(self) -> None:
        self._last_action = None
        self._last_yank_span = None
        if self._cursor <= 0:
            return
        self._push_undo()
        self._value = self._value[: self._cursor - 1] + self._value[self._cursor :]
        self._cursor -= 1

    def _forward_delete(self) -> None:
        self._last_action = None
        self._last_yank_span = None
        if self._cursor >= len(self._value):
            return
        self._push_undo()
        self._value = self._value[: self._cursor] + self._value[self._cursor + 1 :]

    def _move_left(self) -> None:
        self._last_action = None
        if self._cursor > 0:
            self._cursor -= 1

    def _move_right(self) -> None:
        self._last_action = None
        if self._cursor < len(self._value):
            self._cursor += 1

    def _move_word_backwards(self) -> None:
        if self._cursor == 0:
            return
        self._last_action = None
        while self._cursor > 0 and self._value[self._cursor - 1].isspace():
            self._cursor -= 1
        if self._cursor == 0:
            return
        if _is_punctuation(self._value[self._cursor - 1]):
            while self._cursor > 0 and _is_punctuation(self._value[self._cursor - 1]):
                self._cursor -= 1
            return
        while (
            self._cursor > 0
            and (not self._value[self._cursor - 1].isspace())
            and (not _is_punctuation(self._value[self._cursor - 1]))
        ):
            self._cursor -= 1

    def _move_word_forwards(self) -> None:
        if self._cursor >= len(self._value):
            return
        self._last_action = None
        n = len(self._value)
        while self._cursor < n and self._value[self._cursor].isspace():
            self._cursor += 1
        if self._cursor >= n:
            return
        if _is_punctuation(self._value[self._cursor]):
            while self._cursor < n and _is_punctuation(self._value[self._cursor]):
                self._cursor += 1
            return
        while (
            self._cursor < n
            and (not self._value[self._cursor].isspace())
            and (not _is_punctuation(self._value[self._cursor]))
        ):
            self._cursor += 1

    def _delete_to_line_start(self) -> None:
        if self._cursor == 0:
            return
        self._push_undo()
        deleted = self._value[: self._cursor]
        self._kill_ring.push(deleted, prepend=True, accumulate=self._last_action == "kill")
        self._last_action = "kill"
        self._last_yank_span = None
        self._value = self._value[self._cursor :]
        self._cursor = 0

    def _delete_to_line_end(self) -> None:
        if self._cursor >= len(self._value):
            return
        self._push_undo()
        deleted = self._value[self._cursor :]
        self._kill_ring.push(deleted, prepend=False, accumulate=self._last_action == "kill")
        self._last_action = "kill"
        self._last_yank_span = None
        self._value = self._value[: self._cursor]

    def _delete_word_backwards(self) -> None:
        if self._cursor == 0:
            return
        was_kill = self._last_action == "kill"
        self._push_undo()
        old_cursor = self._cursor
        self._move_word_backwards()
        delete_from = self._cursor
        self._cursor = old_cursor
        deleted = self._value[delete_from : self._cursor]
        self._kill_ring.push(deleted, prepend=True, accumulate=was_kill)
        self._last_action = "kill"
        self._last_yank_span = None
        self._value = self._value[:delete_from] + self._value[self._cursor :]
        self._cursor = delete_from

    def _delete_word_forwards(self) -> None:
        if self._cursor >= len(self._value):
            return
        was_kill = self._last_action == "kill"
        self._push_undo()
        old_cursor = self._cursor
        self._move_word_forwards()
        delete_to = self._cursor
        self._cursor = old_cursor
        deleted = self._value[self._cursor : delete_to]
        self._kill_ring.push(deleted, prepend=False, accumulate=was_kill)
        self._last_action = "kill"
        self._last_yank_span = None
        self._value = self._value[: self._cursor] + self._value[delete_to:]

    def _yank(self) -> None:
        text = self._kill_ring.peek()
        if not text:
            return
        self._push_undo()
        start = self._cursor
        self._value = self._value[: self._cursor] + text + self._value[self._cursor :]
        self._cursor += len(text)
        self._last_action = "yank"
        self._last_yank_span = (start, start + len(text))

    def _yank_pop(self) -> None:
        if self._last_action != "yank" or self._kill_ring.length <= 1 or self._last_yank_span is None:
            return
        self._push_undo()
        start, end = self._last_yank_span
        self._value = self._value[:start] + self._value[end:]
        self._cursor = start
        self._kill_ring.rotate()
        text = self._kill_ring.peek()
        self._value = self._value[: self._cursor] + text + self._value[self._cursor :]
        self._cursor += len(text)
        self._last_action = "yank"
        self._last_yank_span = (start, start + len(text))

    def _push_undo(self) -> None:
        self._undo_stack.push(InputState(value=self._value, cursor=self._cursor))

    def _undo(self) -> None:
        prev = self._undo_stack.undo(InputState(value=self._value, cursor=self._cursor))
        if prev is None:
            return
        self._value = prev.value
        self._cursor = prev.cursor
        self._last_action = None
        self._last_yank_span = None

    def _column_of_index(self, idx: int) -> int:
        return visible_width(self._value[: max(0, min(idx, len(self._value)))])

    def _slice_by_columns(self, text: str, start_col: int, width: int) -> str:
        if width <= 0:
            return ""
        out: list[str] = []
        col = 0
        end_col = start_col + width
        for ch in text:
            ch_w = visible_width(ch)
            next_col = col + ch_w
            if next_col <= start_col:
                col = next_col
                continue
            if col >= end_col:
                break
            # Strict clipping for wide characters at slice boundaries:
            # skip a char if it starts before start_col, and stop if it would
            # extend beyond end_col.
            if col < start_col:
                col = next_col
                continue
            if next_col > end_col:
                break
            out.append(ch)
            col = next_col
        return "".join(out)
