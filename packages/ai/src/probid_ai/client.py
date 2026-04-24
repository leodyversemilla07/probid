"""API client for AI provider HTTP calls."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from collections.abc import Generator
from typing import Any

from probid_ai.types import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    StreamChunk,
)


class APIError(Exception):
    """Raised when API call fails."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class BaseAIClient(ABC):
    """Abstract base for AI provider clients."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None):
        self.api_key = api_key or self._default_api_key()
        self.base_url = base_url or self._default_base_url()

    @abstractmethod
    def _default_api_key(self) -> str:
        pass

    @abstractmethod
    def _default_base_url(self) -> str:
        pass

    @abstractmethod
    def _headers(self) -> dict[str, str]:
        pass

    @abstractmethod
    def _parse_response(self, data: dict[str, Any]) -> ChatCompletionResponse:
        pass

    @abstractmethod
    def _parse_stream_chunk(self, data: dict[str, Any]) -> StreamChunk:
        pass

    @abstractmethod
    def chat_completions(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        """Synchronous chat completion."""
        pass

    @abstractmethod
    def chat_completions_stream(self, request: ChatCompletionRequest) -> Generator[StreamChunk, None, None]:
        """Streaming chat completion."""
        pass


def getenv_or_raise(key: str) -> str:
    """Get env var or raise helpful error."""
    value = os.environ.get(key)
    if not value:
        raise ValueError(f"Required environment variable not set: {key}")
    return value
