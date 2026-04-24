"""Editor adapter with pi-tui compatible API surface."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from probid_tui.autocomplete import AutocompleteProvider
from probid_tui.core.editor import Editor as CoreEditor


@dataclass(frozen=True)
class EditorTheme:
    border_color: Callable[[str], str] = lambda s: s
    select_list: object | None = None


@dataclass(frozen=True)
class EditorOptions:
    padding_x: int = 0
    autocomplete_max_visible: int = 5


class Editor(CoreEditor):
    def __init__(
        self,
        tui=None,
        theme: EditorTheme | None = None,
        options: EditorOptions | None = None,
    ):
        opts = options or EditorOptions()
        super().__init__(max_visible_lines=5)
        self.tui = tui
        self.theme = theme or EditorTheme()
        self.options = opts
        self.border_color = self.theme.border_color
        self.disable_submit = False
        self.onSubmit: Callable[[str], None] | None = None
        self.onChange: Callable[[str], None] | None = None
        self._autocomplete_provider: AutocompleteProvider | None = None
        self.set_on_submit(self._on_submit)

    def _on_submit(self, text: str) -> None:
        if self.disable_submit:
            return
        if self.onSubmit is not None:
            self.onSubmit(text)

    def get_text(self) -> str:
        return self.get_value()

    def set_text(self, text: str) -> None:
        self.set_value(text)

    def add_to_history(self, text: str) -> None:
        if text:
            self._history.append(text)  # noqa: SLF001 - compatibility surface

    def insert_text_at_cursor(self, text: str) -> None:
        self._insert_text(text)  # noqa: SLF001 - compatibility surface

    def get_expanded_text(self) -> str:
        return self.get_value()

    def set_padding_x(self, _padding: int) -> None:
        # kept for API parity; current core editor already handles display rails.
        return

    def set_autocomplete_max_visible(self, _max_visible: int) -> None:
        return

    def set_autocomplete_provider(self, provider: AutocompleteProvider) -> None:
        self._autocomplete_provider = provider

        def _autocomplete(prefix: str) -> list[str]:
            suggestions = provider.get_suggestions(prefix, len(prefix), force=True)
            if suggestions is None:
                return []
            return [item.value for item in suggestions.items]

        self._autocomplete = _autocomplete  # noqa: SLF001 - compatibility surface
        self._refresh_completions()  # noqa: SLF001 - compatibility surface

    def handle_input(self, data: bytes) -> bool:
        before = self.get_value()
        consumed = super()._process_input(data)
        after = self.get_value()
        if consumed and after != before and self.onChange is not None:
            self.onChange(after)
        return consumed
