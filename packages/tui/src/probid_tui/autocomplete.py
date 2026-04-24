"""Autocomplete providers compatible with pi-tui naming and contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from probid_tui.fuzzy import fuzzy_filter


@dataclass(frozen=True)
class AutocompleteItem:
    value: str
    label: str
    description: str = ""


@dataclass(frozen=True)
class SlashCommand:
    name: str
    description: str = ""


@dataclass(frozen=True)
class AutocompleteSuggestions:
    items: list[AutocompleteItem]
    start: int
    end: int


class AutocompleteProvider(Protocol):
    def get_suggestions(
        self,
        text: str,
        cursor_pos: int | None = None,
        force: bool = False,
    ) -> AutocompleteSuggestions | None: ...


class CombinedAutocompleteProvider:
    """Slash-command and file-path autocomplete."""

    def __init__(
        self,
        slash_commands: list[SlashCommand] | None = None,
        base_path: str | Path | None = None,
    ):
        self.slash_commands = list(slash_commands or [])
        self.base_path = Path(base_path or Path.cwd())

    def get_suggestions(
        self,
        text: str,
        cursor_pos: int | None = None,
        force: bool = False,
    ) -> AutocompleteSuggestions | None:
        if cursor_pos is None:
            cursor_pos = len(text)
        prefix_text = (text or "")[: max(0, cursor_pos)]
        token_start = prefix_text.rfind(" ") + 1
        token = prefix_text[token_start:]

        if token.startswith("/"):
            q = token[1:]
            commands = self.slash_commands
            if q:
                commands = fuzzy_filter(commands, q, lambda c: c.name)
            items = [
                AutocompleteItem(
                    value=f"/{cmd.name}",
                    label=f"/{cmd.name}",
                    description=cmd.description,
                )
                for cmd in commands[:20]
            ]
            return AutocompleteSuggestions(items=items, start=token_start, end=cursor_pos)

        # Path completion on explicit force (Tab) or common path starters.
        if not force and not token.startswith(("~", ".", "/", "@")):
            return None

        token_for_path = token[1:] if token.startswith("@") else token
        if not token_for_path:
            token_for_path = "."

        expanded = Path(token_for_path).expanduser()
        if not expanded.is_absolute():
            expanded = self.base_path / expanded

        parent = expanded if expanded.is_dir() else expanded.parent
        needle = "" if expanded.is_dir() else expanded.name
        if not parent.exists():
            return None

        candidates: list[AutocompleteItem] = []
        for child in sorted(parent.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
            if needle and needle.lower() not in child.name.lower():
                continue
            display = str(child)
            if child.is_dir():
                display += "/"
            if token.startswith("@"):
                display = "@" + display
            candidates.append(
                AutocompleteItem(
                    value=display,
                    label=display,
                    description="directory" if child.is_dir() else "file",
                )
            )
            if len(candidates) >= 30:
                break

        if not candidates:
            return None
        return AutocompleteSuggestions(items=candidates, start=token_start, end=cursor_pos)
