"""Anthropic-compatible API client for OpenCode Zen and other providers."""

from __future__ import annotations

import json
import os
from collections.abc import Callable, Generator
from typing import Any

import httplib2

from probid_ai.client import APIError, BaseAIClient, getenv_or_raise
from probid_ai.types import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Message,
    StreamChunk,
)

# Try to use probid auth storage, fall back to env vars
try:
    from probid_probing_agent.core.auth_storage import (
        get_api_key as _get_probid_api_key,
    )
except ImportError:
    _get_probid_api_key: Callable[[str], str] | None = None


def _get_provider_api_key(provider: str = "anthropic") -> str:
    """Get API key for a provider, checking auth storage first."""
    provider = provider.strip().lower()

    # Try auth storage first
    if _get_probid_api_key:
        key = _get_probid_api_key(provider)
        if key:
            return key
        # Also try 'opencode' for any provider that might map to it
        if provider != "opencode":
            key = _get_probid_api_key("opencode")
            if key:
                return key

    env_map = {
        "anthropic": "ANTHROPIC_API_KEY",
        "opencode": "OPENCODE_API_KEY",
        "minimax": "MINIMAX_API_KEY",
    }
    env_var = env_map.get(provider)
    if env_var:
        return os.environ.get(env_var, "")
    # Fall back to env var
    return os.environ.get("OPENCODE_API_KEY", "") or os.environ.get("ANTHROPIC_API_KEY", "")


class AnthropicClient(BaseAIClient):
    """Anthropic-compatible API client for OpenCode Zen and similar providers."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        provider_name: str = "anthropic",
    ):
        self._provider_name = provider_name
        super().__init__(api_key, base_url)

    def _default_api_key(self) -> str:
        provider_key = _get_provider_api_key(self._provider_name)
        if provider_key:
            return provider_key
        return getenv_or_raise("ANTHROPIC_API_KEY")

    def _default_base_url(self) -> str:
        # Check for provider-specific base URL
        if self._provider_name == "opencode":
            return os.environ.get("ANTHROPIC_BASE_URL", "https://opencode.ai/zen")
        if self._provider_name == "minimax":
            return os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimax.io")
        if self._provider_name == "minimax-cn":
            return os.environ.get("ANTHROPIC_BASE_URL", "https://api.minimaxi.com")
        return os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com")

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def _parse_response(self, data: dict[str, Any]) -> ChatCompletionResponse:
        # Anthropic returns in a different format, convert to our format
        content = data.get("content", [])
        if isinstance(content, list) and len(content) > 0:
            text_content = ""
            for block in content:
                if block.get("type") == "text":
                    text_content += block.get("text", "")
        else:
            text_content = str(content) if content else ""

        choices = [
            ChatCompletionChoice(
                index=0,
                message=Message(
                    role="assistant",
                    content=text_content,
                ),
                finish_reason=data.get("stop_reason", "end_turn"),
            )
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
        content = delta.get("text", "")
        return StreamChunk(
            delta=Message(
                role="assistant",
                content=content,
            ),
            index=0,
            finish_reason=delta.get("stop_reason"),
        )

    def chat_completions(self, request: ChatCompletionRequest) -> ChatCompletionResponse:
        # Convert OpenAI-style request to Anthropic format
        url = f"{self.base_url}/v1/messages"

        # Preserve all non-system turns and combine system prompts.
        system_parts: list[str] = []
        messages: list[dict[str, str]] = []
        for msg in request.messages:
            if msg.role == "system":
                system_parts.append(msg.content)
            elif msg.role in {"user", "assistant"}:
                messages.append({"role": msg.role, "content": msg.content})

        payload = {
            "model": request.model,
            "max_tokens": request.max_tokens or 1024,
            "messages": messages or [{"role": "user", "content": ""}],
        }
        if system_parts:
            payload["system"] = "\n\n".join(part for part in system_parts if part)
        if request.temperature is not None:
            payload["temperature"] = int(request.temperature)

        # Use httplib2 for proper header handling
        h = httplib2.Http()
        resp, content = h.request(url, "POST", body=json.dumps(payload), headers=self._headers())

        if resp.status >= 400:
            raise APIError(f"API error: {content.decode('utf-8')}", resp.status)

        data = json.loads(content.decode("utf-8"))
        return self._parse_response(data)

    def chat_completions_stream(self, request: ChatCompletionRequest) -> Generator[StreamChunk, None, None]:
        response = self.chat_completions(request)
        if not response.choices:
            return
        message = response.choices[0].message
        yield StreamChunk(
            delta=Message(role=message.role, content=message.content),
            index=0,
            finish_reason=response.choices[0].finish_reason,
        )
