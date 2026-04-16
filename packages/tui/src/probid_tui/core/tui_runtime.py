"""Differential TUI runtime with pi-tui compatible overlay controls."""

from __future__ import annotations

import asyncio
import os
import sys
from dataclasses import dataclass
from typing import Any, Callable, Literal

from probid_tui.core.ansi_utils import truncate_to_width
from probid_tui.core.component import Component, Focusable, is_focusable
from probid_tui.core.keys import is_key_release, split_input_sequences
from probid_tui.core.terminal import ProcessTerminal

SYNC_START = "\x1b[?2026h"
SYNC_END = "\x1b[?2026l"
SGR_RESET = "\x1b[0m"
OSC8_RESET = "\x1b]8;;\x1b\\"
CURSOR_MARKER = "\x1b_pi:c\x07"

OverlayAnchor = Literal[
    "center",
    "top-left",
    "top-right",
    "bottom-left",
    "bottom-right",
    "top-center",
    "bottom-center",
    "left-center",
    "right-center",
]
SizeValue = int | str


class Container(Component):
    def __init__(self):
        self._children: list[Component] = []

    @property
    def children(self) -> list[Component]:
        return self._children

    def add_child(self, child: Component) -> None:
        self._children.append(child)

    def remove_child(self, child: Component) -> None:
        if child in self._children:
            self._children.remove(child)

    def clear(self) -> None:
        self._children.clear()

    def render(self, width: int) -> list[str]:
        lines: list[str] = []
        for child in self._children:
            lines.extend(child.render(width))
        return lines

    def invalidate(self) -> None:
        for child in self._children:
            child.invalidate()


@dataclass(frozen=True)
class OverlayMargin:
    top: int = 0
    right: int = 0
    bottom: int = 0
    left: int = 0


@dataclass
class OverlayOptions:
    width: SizeValue = "50%"
    min_width: int | None = None
    max_height: SizeValue = "80%"
    anchor: OverlayAnchor = "center"
    offset_x: int = 0
    offset_y: int = 0
    row: SizeValue | None = None
    col: SizeValue | None = None
    margin: OverlayMargin | int = 1
    visible: Callable[[int, int], bool] | None = None
    non_capturing: bool = False


class OverlayHandle:
    def __init__(self, tui: "TUI", entry: dict[str, Any]):
        self._tui = tui
        self._entry = entry

    def hide(self) -> None:
        self._tui._remove_overlay_entry(self._entry)

    def set_hidden(self, value: bool) -> None:
        self._entry["hidden"] = bool(value)
        if value and self._tui._focused is self._entry["component"]:
            top = self._tui._top_visible_overlay()
            self._tui.set_focus(top["component"] if top else self._entry.get("pre_focus"))
        self._tui.request_render()

    def is_hidden(self) -> bool:
        return bool(self._entry.get("hidden"))

    def focus(self) -> None:
        self._entry["focus_order"] = self._tui._next_focus_order()
        self._tui.set_focus(self._entry["component"])
        self._tui.request_render()

    def unfocus(self) -> None:
        self._tui.set_focus(self._entry.get("pre_focus"))
        self._tui.request_render()

    def is_focused(self) -> bool:
        return self._tui._focused is self._entry["component"]

    # pi-tui style aliases
    setHidden = set_hidden
    isHidden = is_hidden
    isFocused = is_focused


class TUI(Container):
    """Differential renderer over a component tree."""

    def __init__(self, terminal: ProcessTerminal):
        super().__init__()
        self.terminal = terminal
        self._previous_lines: list[str] = []
        self._render_pending = False
        self._focused: Component | None = None
        self._running = False
        self._last_width = 0
        self._clear_on_shrink = bool(os.environ.get("PI_CLEAR_ON_SHRINK"))

        self._loop: asyncio.AbstractEventLoop | None = None
        self._input_handler = None
        self._overlays: list[dict[str, Any]] = []
        self._focus_order_counter = 0
        self.terminal.on_resize(lambda _c, _r: self.request_render(force=True))

    def _next_focus_order(self) -> int:
        self._focus_order_counter += 1
        return self._focus_order_counter

    def start(self) -> None:
        self._running = True
        self._loop = asyncio.get_event_loop()
        self._loop.add_reader(sys.stdin.fileno(), self._on_input)
        self.request_render(force=True)

    def stop(self) -> None:
        self._running = False
        if self._loop is not None:
            try:
                self._loop.remove_reader(sys.stdin.fileno())
            except Exception:
                pass
        self.terminal.restore()

    def request_render(self, force: bool = False) -> None:
        if self._loop is None:
            try:
                self._loop = asyncio.get_running_loop()
            except RuntimeError:
                self._do_render(force)
                return
        if self._render_pending and not force:
            return
        self._render_pending = True
        self._loop.call_soon(lambda: self._do_render(force))

    def show_overlay(self, component: Component, options: OverlayOptions | None = None) -> OverlayHandle:
        opts = options or OverlayOptions()
        entry = {
            "component": component,
            "options": opts,
            "hidden": False,
            "pre_focus": self._focused,
            "focus_order": self._next_focus_order(),
        }
        self._overlays.append(entry)
        if not opts.non_capturing and self._is_overlay_visible(entry, *self.terminal.get_size()):
            self.set_focus(component)
        self.request_render()
        return OverlayHandle(self, entry)

    def showOverlay(self, component: Component, options: OverlayOptions | None = None) -> OverlayHandle:
        return self.show_overlay(component, options)

    def hide_overlay(self) -> None:
        top = self._top_visible_overlay()
        if top is None:
            return
        self._remove_overlay_entry(top)

    def hideOverlay(self) -> None:
        self.hide_overlay()

    def has_overlay(self) -> bool:
        w, h = self.terminal.get_size()
        return any(self._is_overlay_visible(entry, w, h) for entry in self._overlays)

    def hasOverlay(self) -> bool:
        return self.has_overlay()

    def _remove_overlay_entry(self, entry: dict[str, Any]) -> None:
        if entry not in self._overlays:
            return
        self._overlays.remove(entry)
        if self._focused is entry["component"]:
            top = self._top_visible_overlay()
            self.set_focus(top["component"] if top else entry.get("pre_focus"))
        self.request_render()

    def _do_render(self, force: bool = False) -> None:
        self._render_pending = False
        width, height = self.terminal.get_size()

        new_lines = self.render(width)
        new_lines = self._composite_overlays(new_lines, width, height)
        new_lines = [line.replace(CURSOR_MARKER, "") + SGR_RESET + OSC8_RESET for line in new_lines]

        prev = self._previous_lines
        out = SYNC_START
        if force or width != self._last_width:
            out += self._full_redraw(new_lines)
        elif self._clear_on_shrink and len(new_lines) < len(prev):
            out += self._full_redraw(new_lines)
        else:
            out += self._diff_render(prev, new_lines)
        out += SYNC_END

        self.terminal.write(out)
        self._previous_lines = new_lines
        self._last_width = width

    def _resolve_dimension(self, value: SizeValue | None, total: int, fallback: int | None = None) -> int:
        if value is None:
            return fallback if fallback is not None else max(1, total // 2)
        if isinstance(value, int):
            return max(1, min(total, value))
        text = str(value).strip()
        if text.endswith("%"):
            try:
                pct = float(text[:-1])
            except ValueError:
                return fallback if fallback is not None else max(1, total // 2)
            return max(1, min(total, int(total * (pct / 100.0))))
        try:
            return max(1, min(total, int(text)))
        except ValueError:
            return fallback if fallback is not None else max(1, total // 2)

    def _normalize_margin(self, margin: OverlayMargin | int) -> OverlayMargin:
        if isinstance(margin, OverlayMargin):
            return margin
        m = max(0, int(margin))
        return OverlayMargin(top=m, right=m, bottom=m, left=m)

    def _resolve_anchor_position(
        self,
        anchor: OverlayAnchor,
        term_w: int,
        term_h: int,
        overlay_w: int,
        overlay_h: int,
        margin: OverlayMargin,
    ) -> tuple[int, int]:
        avail_w = max(1, term_w - margin.left - margin.right)
        avail_h = max(1, term_h - margin.top - margin.bottom)

        if anchor in {"top-left", "left-center", "bottom-left"}:
            col = margin.left
        elif anchor in {"top-right", "right-center", "bottom-right"}:
            col = term_w - margin.right - overlay_w
        else:
            col = margin.left + max(0, (avail_w - overlay_w) // 2)

        if anchor in {"top-left", "top-center", "top-right"}:
            row = margin.top
        elif anchor in {"bottom-left", "bottom-center", "bottom-right"}:
            row = term_h - margin.bottom - overlay_h
        else:
            row = margin.top + max(0, (avail_h - overlay_h) // 2)

        return col, row

    def _resolve_overlay_layout(
        self,
        options: OverlayOptions,
        overlay_h: int,
        term_w: int,
        term_h: int,
    ) -> tuple[int, int, int, int]:
        margin = self._normalize_margin(options.margin)
        max_w = max(1, term_w - margin.left - margin.right)
        width = self._resolve_dimension(options.width, max_w, fallback=min(80, max_w))
        if options.min_width is not None:
            width = max(1, min(max_w, max(options.min_width, width)))
        max_h = self._resolve_dimension(options.max_height, max(1, term_h), fallback=max(1, term_h))
        overlay_h = min(overlay_h, max_h)

        if options.row is not None:
            if isinstance(options.row, str) and options.row.endswith("%"):
                pct = max(0.0, min(100.0, float(options.row[:-1] or 0)))
                row = margin.top + int((max(0, term_h - margin.top - margin.bottom - overlay_h) * pct) / 100.0)
            else:
                row = int(options.row)
        else:
            _col_anchor, row = self._resolve_anchor_position(options.anchor, term_w, term_h, width, overlay_h, margin)

        if options.col is not None:
            if isinstance(options.col, str) and options.col.endswith("%"):
                pct = max(0.0, min(100.0, float(options.col[:-1] or 0)))
                col = margin.left + int((max(0, term_w - margin.left - margin.right - width) * pct) / 100.0)
            else:
                col = int(options.col)
        else:
            col, _row_anchor = self._resolve_anchor_position(options.anchor, term_w, term_h, width, overlay_h, margin)

        col += options.offset_x
        row += options.offset_y
        col = max(margin.left, min(term_w - margin.right - width, col))
        row = max(margin.top, min(term_h - margin.bottom - overlay_h, row))
        return width, max_h, col, row

    def _is_overlay_visible(self, entry: dict[str, Any], width: int, height: int) -> bool:
        if entry.get("hidden"):
            return False
        options: OverlayOptions = entry["options"]
        if options.visible is not None and not options.visible(width, height):
            return False
        return True

    def _top_visible_overlay(self) -> dict[str, Any] | None:
        width, height = self.terminal.get_size()
        visible = [e for e in self._overlays if self._is_overlay_visible(e, width, height)]
        if not visible:
            return None
        visible.sort(key=lambda e: e.get("focus_order", 0), reverse=True)
        return visible[0]

    def _composite_overlays(self, base_lines: list[str], width: int, height: int) -> list[str]:
        canvas_height = max(height, len(base_lines), 1)
        canvas = [truncate_to_width(line, width, pad=True) for line in base_lines]
        if len(canvas) < canvas_height:
            canvas.extend([" " * width for _ in range(canvas_height - len(canvas))])

        visible_entries = [e for e in self._overlays if self._is_overlay_visible(e, width, height)]
        visible_entries.sort(key=lambda e: e.get("focus_order", 0))

        for entry in visible_entries:
            options: OverlayOptions = entry["options"]
            est_w, max_h, col, row = self._resolve_overlay_layout(options, 1, width, height)
            overlay_lines = entry["component"].render(est_w)
            if max_h > 0:
                overlay_lines = overlay_lines[:max_h]
            if not overlay_lines:
                continue
            overlay_w, _max_h2, col, row = self._resolve_overlay_layout(options, len(overlay_lines), width, height)

            for i, line in enumerate(overlay_lines):
                dest_row = row + i
                if not (0 <= dest_row < canvas_height):
                    continue
                base = canvas[dest_row]
                overlay_text = truncate_to_width(line, max(0, width - col), pad=False)
                if not overlay_text:
                    continue
                prefix = base[:col]
                suffix_idx = min(width, col + len(overlay_text))
                suffix = base[suffix_idx:]
                canvas[dest_row] = truncate_to_width(prefix + overlay_text + suffix, width, pad=True)

        while canvas and canvas[-1].strip() == "":
            canvas.pop()
        return canvas or [""]

    def _full_redraw(self, new_lines: list[str]) -> str:
        n = len(self._previous_lines)
        # Cursor ends on the last rendered line; move back to top of TUI region.
        lines_up = max(0, n - 1)
        out = f"\x1b[{lines_up}A\r" if lines_up else "\r"
        out += "\x1b[J"
        out += "\r\n".join(new_lines)
        return out

    def _diff_render(self, prev: list[str], curr: list[str]) -> str:
        first_diff = None
        for i in range(min(len(prev), len(curr))):
            if prev[i] != curr[i]:
                first_diff = i
                break

        if first_diff is None:
            if len(prev) == len(curr):
                return ""
            first_diff = min(len(prev), len(curr))

        # Cursor ends on previous render's last line; move to first changed line.
        lines_from_end = max(0, len(prev) - first_diff - 1)
        out = f"\x1b[{lines_from_end}A\r" if lines_from_end else "\r"
        out += "\x1b[J"
        out += "\r\n".join(curr[first_diff:])
        return out

    def set_focus(self, component: Component | None) -> None:
        if is_focusable(self._focused):
            self._focused.focused = False  # type: ignore[attr-defined]
        self._focused = component
        if is_focusable(component):
            component.focused = True  # type: ignore[attr-defined]
        self.request_render()

    def set_input_handler(self, handler) -> None:
        self._input_handler = handler

    def _on_input(self) -> None:
        raw = os.read(sys.stdin.fileno(), 4096)
        for data in split_input_sequences(raw):
            consumed = False
            if self._focused is not None:
                if is_key_release(data) and not getattr(self._focused, "wants_key_release", False):
                    continue
                consumed = bool(self._focused.handle_input(data))
            if not consumed and self._input_handler is not None:
                self._input_handler(data)
        self.request_render()
