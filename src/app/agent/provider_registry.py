"""Provider registry for probid agent runtime."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


ProviderHandler = Callable[[str, Any], dict[str, Any]]


@dataclass(frozen=True)
class Provider:
    name: str
    handle: ProviderHandler


@dataclass(frozen=True)
class _RegisteredProvider:
    provider: Provider
    source_id: str | None = None


_registry: dict[str, _RegisteredProvider] = {}


def register_provider(provider: Provider, source_id: str | None = None) -> None:
    _registry[provider.name] = _RegisteredProvider(provider=provider, source_id=source_id)


def get_provider(name: str) -> Provider | None:
    entry = _registry.get(name)
    return entry.provider if entry else None


def list_providers() -> list[str]:
    return sorted(_registry.keys())


def unregister_providers(source_id: str) -> None:
    to_remove = [key for key, entry in _registry.items() if entry.source_id == source_id]
    for key in to_remove:
        del _registry[key]


def clear_providers() -> None:
    _registry.clear()
