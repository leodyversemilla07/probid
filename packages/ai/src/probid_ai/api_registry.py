"""API provider registry with stream wrappers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


ApiStreamFn = Callable[[Any, Any, Any | None], Any]


@dataclass(frozen=True)
class ApiProvider:
    api: str
    stream: ApiStreamFn
    stream_simple: ApiStreamFn


@dataclass(frozen=True)
class _RegisteredApiProvider:
    provider: ApiProvider
    source_id: str | None = None


_registry: dict[str, _RegisteredApiProvider] = {}


def _wrap_stream(api: str, stream: ApiStreamFn) -> ApiStreamFn:
    def _wrapped(model: Any, context: Any, options: Any | None = None) -> Any:
        model_api = getattr(model, "api", None)
        if model_api != api:
            raise ValueError(f"Mismatched api: {model_api} expected {api}")
        return stream(model, context, options)

    return _wrapped


def register_api_provider(provider: ApiProvider, source_id: str | None = None) -> None:
    _registry[provider.api] = _RegisteredApiProvider(
        provider=ApiProvider(
            api=provider.api,
            stream=_wrap_stream(provider.api, provider.stream),
            stream_simple=_wrap_stream(provider.api, provider.stream_simple),
        ),
        source_id=source_id,
    )


def get_api_provider(api: str) -> ApiProvider | None:
    entry = _registry.get(api)
    return entry.provider if entry is not None else None


def get_api_providers() -> list[ApiProvider]:
    return [entry.provider for entry in _registry.values()]


def unregister_api_providers(source_id: str) -> None:
    to_remove = [api for api, entry in _registry.items() if entry.source_id == source_id]
    for api in to_remove:
        del _registry[api]


def clear_api_providers() -> None:
    _registry.clear()


# pi-style aliases
registerApiProvider = register_api_provider
getApiProvider = get_api_provider
getApiProviders = get_api_providers
unregisterApiProviders = unregister_api_providers
clearApiProviders = clear_api_providers
