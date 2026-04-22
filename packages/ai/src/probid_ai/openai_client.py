"""OpenAI-compatible client implementation."""

from __future__ import annotations

import json
from typing import Any, Generator
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from probid_ai.client import APIError, BaseAIClient, getenv_or_raise
from probid_ai.types import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Message,
    StreamChunk,
)


class OpenAIClient(BaseAIClient):
    """OpenAI-compatible API client (works with OpenAI, Anthropic via adapter, etc.)."""

    def __init__(self, api_key: str | None = None, base_url: str | None = None, provider_name: str = "openai"):
        self._provider_name = provider_name
        super().__init__(api_key, base_url)

    def _default_api_key(self) -> str:
        # Try provider-specific key, then generic fallback
        provider_key = _get_provider_api_key(self._provider_name)
        if provider_key:
            return provider_key
        if self._provider_name == "opencode":
            return getenv_or_raise("OPENCODE_API_KEY")
        return getenv_or_raise("OPENAI_API_KEY")

    def _default_base_url(self) -> str:
        return os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def _parse_response(self, data: dict[str, Any]) -> ChatCompletionResponse:
        choices = [
            ChatCompletionChoice(
                index=c.get("index", 0),
                message=Message(
                    role=c.get("message", {}).get("role", "assistant"),
                    content=c.get("message", {}).get("content", ""),
                ),
                finish_reason=c.get("finish_reason", ""),
            )
            for c in data.get("choices", [])
        ]
        return ChatCompletionResponse(
            id=data.get("id", ""),
            created=data.get("created", 0),
            model=data.get("model", ""),
            choices=choices,
            usage=data.get("usage"),
        )

    def _parse_stream_chunk(self, data: dict[str, Any]) -> StreamChunk:
        delta = data.get("delta", {})
        return StreamChunk(
            delta=Message(
                role=delta.get("role", "assistant"),
                content=delta.get("content", ""),
            ),
            index=data.get("index", 0),
            finish_reason=data.get("finish_reason"),
        )

    def chat_completions(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": False,
        }

        req = Request(url, data=json.dumps(payload).encode("utf-8"), headers=self._headers(), method="POST")
        try:
            with urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except HTTPError as e:
            body = e.read().decode("utf-8")
            raise APIError(f"API error: {body}", e.code) from e

        return self._parse_response(data)

    def chat_completions_stream(
        self, request: ChatCompletionRequest
    ) -> Generator[StreamChunk, None, None]:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": request.model,
            "messages": [{"role": m.role, "content": m.content} for m in request.messages],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": True,
        }

        req = Request(url, data=json.dumps(payload).encode("utf-8"), headers=self._headers(), method="POST")
        try:
            with urlopen(req) as resp:
                for line in resp:
                    line = line.decode("utf-8").strip()
                    if not line or not line.startswith("data:"):
                        continue
                    if line == "data: [DONE]":
                        return
                    data = json.loads(line[5:])
                    yield self._parse_stream_chunk(data)
        except HTTPError as e:
            body = e.read().decode("utf-8")
            raise APIError(f"API error: {body}", e.code) from e


import os


# Try to use probid auth storage, fall back to env vars
try:
    from probid_probing_agent.core.auth_storage import get_api_key as _get_probid_api_key
except ImportError:
    _get_probid_api_key = None


def _get_provider_api_key(provider: str = "openai") -> str:
    """Get API key for a provider, checking auth storage first."""
    # Try probid auth storage first (if available)
    if _get_probid_api_key:
        key = _get_probid_api_key(provider)
        if key:
            return key
    
    # Fall back to env vars
    env_map = {
        "opencode": "OPENCODE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "anthropic": "ANTHROPIC_API_KEY",
        "google": "GEMINI_API_KEY",
    }
    env_var = env_map.get(provider)
    if env_var:
        return os.environ.get(env_var, "")
    return os.environ.get("OPENAI_API_KEY", "")
