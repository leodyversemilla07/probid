"""OpenAI-compatible client implementation."""

from __future__ import annotations

import json
from typing import Any, Generator
from urllib.request import Request, urlopen
from urllib.error import HTTPError

from probid_ai.client import APIError, BaseAIClient, getenv_or_raise
from probid_ai.env_api_keys import get_env_api_key
from probid_ai.types import (
    ChatCompletionChoice,
    ChatCompletionRequest,
    ChatCompletionResponse,
    Message,
    StreamChunk,
)


class OpenAIClient(BaseAIClient):
    """OpenAI-compatible API client (works with OpenAI, Anthropic via adapter, etc.)."""

    def _default_api_key(self) -> str:
        key = get_env_api_key("openai")
        if key:
            return key
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
