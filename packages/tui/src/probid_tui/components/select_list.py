"""Interactive select list."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from probid_tui.core.ansi_utils import truncate_to_width, visible_width
from probid_tui.core.component import Component
from probid_tui.core.keys import parse_key

DEFAULT_PRIMARY_COLUMN_WIDTH = 32
PRIMARY_COLUMN_GAP = 2
MIN_DESCRIPTION_WIDTH = 10


def _normalize_single_line(text: str) -> str:
    return " ".join((text or "").split())


def _clamp(value: int, min_value: int, max_value: int) -> int:
    return max(min_value, min(max_value, value))


@dataclass(frozen=True)
class SelectItem:
    value: str
    label: str
    description: str = ""


@dataclass(frozen=True)
class SelectListTheme:
    selected_prefix: Callable[[str], str] = lambda x: x
    selected_text: Callable[[str], str] = lambda x: x
    description: Callable[[str], str] = lambda x: x
    scroll_info: Callable[[str], str] = lambda x: x
    no_match: Callable[[str], str] = lambda x: x


@dataclass(frozen=True)
class SelectListTruncatePrimaryContext:
    text: str
    max_width: int
    column_width: int
    item: SelectItem
    is_selected: bool


@dataclass(frozen=True)
class SelectListLayoutOptions:
    min_primary_column_width: int = DEFAULT_PRIMARY_COLUMN_WIDTH
    max_primary_column_width: int = DEFAULT_PRIMARY_COLUMN_WIDTH
    truncate_primary: Callable[[SelectListTruncatePrimaryContext], str] | None = None


class SelectList(Component):
    def __init__(
        self,
        items: list[SelectItem],
        max_visible: int = 5,
        theme: SelectListTheme | None = None,
        layout: SelectListLayoutOptions | None = None,
    ):
        self._all_items = list(items)
        self._filtered_items = list(items)
        self.max_visible = max(1, int(max_visible))
        self.theme = theme or SelectListTheme()
        self.layout = layout or SelectListLayoutOptions()
        self.index = 0
        self.on_select: Callable[[SelectItem], None] | None = None
        self.on_cancel: Callable[[], None] | None = None
        self.on_selection_change: Callable[[SelectItem], None] | None = None

    def set_filter(self, query: str) -> None:
        q = (query or "").lower().strip()
        if not q:
            self._filtered_items = list(self._all_items)
        else:
            # pi-tui behavior: filter primarily by prefix on command value
            self._filtered_items = [item for item in self._all_items if item.value.lower().startswith(q)]
        self.index = min(self.index, max(0, len(self._filtered_items) - 1))
        self._emit_selection_change()

    def set_selected_index(self, index: int) -> None:
        self.index = _clamp(index, 0, max(0, len(self._filtered_items) - 1))
        self._emit_selection_change()

    @property
    def items(self) -> list[SelectItem]:
        return list(self._filtered_items)

    def _emit_selection_change(self) -> None:
        if self.on_selection_change and self._filtered_items:
            self.on_selection_change(self._filtered_items[self.index])

    def handle_input(self, data: bytes) -> bool:
        key = parse_key(data)
        if key == "up":
            if self._filtered_items:
                self.index = self.index - 1 if self.index > 0 else len(self._filtered_items) - 1
                self._emit_selection_change()
            return True
        if key == "down":
            if self._filtered_items:
                self.index = self.index + 1 if self.index < len(self._filtered_items) - 1 else 0
                self._emit_selection_change()
            return True
        if key == "enter":
            if self.on_select and self._filtered_items:
                self.on_select(self._filtered_items[self.index])
            return True
        if key in {"escape", "ctrl+c"}:
            if self.on_cancel:
                self.on_cancel()
            return True
        return False

    def render(self, width: int) -> list[str]:
        width = max(1, width)
        lines: list[str] = []

        if not self._filtered_items:
            lines.append(self.theme.no_match("  No matching commands"))
            return lines

        primary_column_width = self._get_primary_column_width()
        start = max(0, min(self.index - (self.max_visible // 2), len(self._filtered_items) - self.max_visible))
        end = min(start + self.max_visible, len(self._filtered_items))

        for i in range(start, end):
            item = self._filtered_items[i]
            lines.append(self._render_item(item, is_selected=(i == self.index), width=width, primary_column_width=primary_column_width))

        if start > 0 or end < len(self._filtered_items):
            lines.append(self.theme.scroll_info(truncate_to_width(f"  ({self.index + 1}/{len(self._filtered_items)})", width - 2, pad=False)))
        return lines

    def _render_item(self, item: SelectItem, is_selected: bool, width: int, primary_column_width: int) -> str:
        prefix = "→ " if is_selected else "  "
        prefix_width = visible_width(prefix)
        description = _normalize_single_line(item.description)
        if description and width > 40:
            effective_primary = max(1, min(primary_column_width, width - prefix_width - 4))
            max_primary_width = max(1, effective_primary - PRIMARY_COLUMN_GAP)
            primary = self._truncate_primary(item, is_selected, max_primary_width, effective_primary)
            primary_w = visible_width(primary)
            spacing = " " * max(1, effective_primary - primary_w)
            desc_start = prefix_width + primary_w + len(spacing)
            remaining = width - desc_start - 2
            if remaining > MIN_DESCRIPTION_WIDTH:
                desc = truncate_to_width(description, remaining, pad=False)
                if is_selected:
                    return self.theme.selected_text(f"{prefix}{primary}{spacing}{desc}")
                return prefix + primary + self.theme.description(spacing + desc)

        max_primary = max(1, width - prefix_width - 2)
        primary = self._truncate_primary(item, is_selected, max_primary, max_primary)
        if is_selected:
            return self.theme.selected_text(f"{prefix}{primary}")
        return prefix + primary

    def _get_primary_column_width(self) -> int:
        min_width, max_width = self._get_primary_column_bounds()
        widest = 0
        for item in self._filtered_items:
            widest = max(widest, visible_width(self._display_value(item)) + PRIMARY_COLUMN_GAP)
        return _clamp(widest, min_width, max_width)

    def _get_primary_column_bounds(self) -> tuple[int, int]:
        raw_min = self.layout.min_primary_column_width
        raw_max = self.layout.max_primary_column_width
        min_width = max(1, min(raw_min, raw_max))
        max_width = max(1, max(raw_min, raw_max))
        return min_width, max_width

    def _truncate_primary(self, item: SelectItem, is_selected: bool, max_width: int, column_width: int) -> str:
        text = self._display_value(item)
        if self.layout.truncate_primary is not None:
            text = self.layout.truncate_primary(
                SelectListTruncatePrimaryContext(
                    text=text,
                    max_width=max_width,
                    column_width=column_width,
                    item=item,
                    is_selected=is_selected,
                )
            )
        return truncate_to_width(text, max_width, pad=False)

    def _display_value(self, item: SelectItem) -> str:
        return item.label or item.value
