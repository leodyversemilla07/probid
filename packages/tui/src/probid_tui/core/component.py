"""Core component contracts for probid TUI runtime."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Component(ABC):
    """Renderable TUI component."""

    wants_key_release: bool = False

    @abstractmethod
    def render(self, width: int) -> list[str]:
        """Return one string per line within the provided visible width."""

    # handle_input can be replaced at runtime with any callable.
    # If not set, the component's _process_input method is used as fallback.
    handle_input: Any = None

    def _process_input(self, data: bytes) -> bool:
        """Default input processing - override in subclasses."""
        return False

    def invalidate(self) -> None:
        """Clear component-local caches, if any."""
        return


class Focusable(ABC):
    """Component that can receive focus and expose cursor position."""

    focused: bool = False

    def get_cursor_position(self) -> tuple[int, int] | None:
        """Return (row, col) cursor position in component-local coordinates."""
        return None


def is_focusable(component: Component | None) -> bool:
    return component is not None and hasattr(component, "focused")


# pi-tui style alias
isFocusable = is_focusable
