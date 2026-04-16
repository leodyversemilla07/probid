"""Keybinding registry and defaults (pi-tui compatible surface)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


Keybinding = str
KeybindingsConfig = dict[str, str | list[str] | None]


class Keybindings(TypedDict, total=False):
    submit: list[str]
    newline: list[str]
    up: list[str]
    down: list[str]
    left: list[str]
    right: list[str]
    cancel: list[str]


@dataclass(frozen=True)
class KeybindingDefinition:
    id: str
    description: str
    default: list[str]


KeybindingDefinitions = dict[str, KeybindingDefinition]


@dataclass(frozen=True)
class KeybindingConflict:
    key: str
    bindings: list[str]


TUI_KEYBINDINGS: KeybindingDefinitions = {
    "submit": KeybindingDefinition("submit", "Submit input", ["enter"]),
    "newline": KeybindingDefinition("newline", "Insert newline", ["shift+enter", "ctrl+enter", "alt+enter"]),
    "up": KeybindingDefinition("up", "Move up", ["up"]),
    "down": KeybindingDefinition("down", "Move down", ["down"]),
    "left": KeybindingDefinition("left", "Move left", ["left"]),
    "right": KeybindingDefinition("right", "Move right", ["right"]),
    "cancel": KeybindingDefinition("cancel", "Cancel/escape", ["escape", "ctrl+c"]),
}


class KeybindingsManager:
    def __init__(self, config: KeybindingsConfig | None = None):
        self._bindings: dict[str, list[str]] = {k: list(v.default) for k, v in TUI_KEYBINDINGS.items()}
        if config:
            self.apply(config)

    def apply(self, config: KeybindingsConfig) -> None:
        for binding, keys in config.items():
            if keys is None:
                continue
            if isinstance(keys, str):
                self._bindings[binding] = [keys]
            else:
                self._bindings[binding] = [k for k in keys if k]

    def get(self, binding: str) -> list[str]:
        return list(self._bindings.get(binding, []))

    def set(self, binding: str, keys: str | list[str]) -> None:
        self._bindings[binding] = [keys] if isinstance(keys, str) else list(keys)

    def as_dict(self) -> dict[str, list[str]]:
        return {k: list(v) for k, v in self._bindings.items()}

    def find_conflicts(self) -> list[KeybindingConflict]:
        reverse: dict[str, list[str]] = {}
        for binding, keys in self._bindings.items():
            for key in keys:
                reverse.setdefault(key, []).append(binding)
        conflicts: list[KeybindingConflict] = []
        for key, bindings in reverse.items():
            if len(bindings) > 1:
                conflicts.append(KeybindingConflict(key=key, bindings=sorted(bindings)))
        return sorted(conflicts, key=lambda c: c.key)


_keybindings = KeybindingsManager()


def set_keybindings(keybindings: KeybindingsManager) -> None:
    global _keybindings
    _keybindings = keybindings


def get_keybindings() -> KeybindingsManager:
    return _keybindings


# pi-tui style aliases
setKeybindings = set_keybindings
getKeybindings = get_keybindings

