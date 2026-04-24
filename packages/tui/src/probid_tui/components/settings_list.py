"""Settings list component with value cycling."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from probid_tui.components.select_list import SelectItem, SelectList, SelectListTheme


@dataclass
class SettingItem:
    id: str
    label: str
    description: str = ""
    current_value: str = ""
    values: list[str] | None = None


@dataclass(frozen=True)
class SettingsListTheme:
    label: Callable[[str, bool], str] = lambda text, _selected: text
    value: Callable[[str, bool], str] = lambda text, _selected: text
    description: Callable[[str], str] = lambda text: text
    cursor: str = "❯ "
    hint: Callable[[str], str] = lambda text: text


class SettingsList(SelectList):
    def __init__(
        self,
        items: list[SettingItem],
        max_visible: int = 10,
        theme: SettingsListTheme | None = None,
        on_change: Callable[[str, str], None] | None = None,
        on_cancel: Callable[[], None] | None = None,
    ):
        self._settings_items = items
        self.settings_theme = theme or SettingsListTheme()
        self._on_change = on_change
        self._on_cancel = on_cancel
        select_items = [
            SelectItem(
                value=item.id,
                label=f"{item.label}: {item.current_value}",
                description=item.description,
            )
            for item in items
        ]
        super().__init__(select_items, max_visible=max_visible, theme=SelectListTheme())

    def update_value(self, item_id: str, new_value: str) -> None:
        for item in self._settings_items:
            if item.id == item_id:
                item.current_value = new_value
        self._all_items = [
            SelectItem(
                value=item.id,
                label=f"{item.label}: {item.current_value}",
                description=item.description,
            )
            for item in self._settings_items
        ]
        self.set_filter("")

    def handle_input(self, data: bytes) -> bool:
        key = super()._process_input(data)
        if key:
            return True
        from probid_tui.core.keys import parse_key

        parsed = parse_key(data)
        if parsed in {"enter", "space"} and self._settings_items:
            item = self._settings_items[self.index]
            if item.values:
                try:
                    pos = item.values.index(item.current_value)
                except ValueError:
                    pos = -1
                item.current_value = item.values[(pos + 1) % len(item.values)]
                self.update_value(item.id, item.current_value)
                if self._on_change:
                    self._on_change(item.id, item.current_value)
            return True
        if parsed in {"escape", "ctrl+c"} and self._on_cancel is not None:
            self._on_cancel()
            return True
        return False
