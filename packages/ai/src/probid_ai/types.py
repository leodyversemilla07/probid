"""Shared types for AI provider layer."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Message:
    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class ChatCompletionRequest:
    model: str
    messages: list[Message]
    temperature: float = 0.7
    max_tokens: int | None = None
    stream: bool = False


@dataclass
class ChatCompletionChoice:
    index: int
    message: Message
    finish_reason: str


@dataclass
class ChatCompletionResponse:
    id: str
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    object: str = "chat.completion"
    usage: dict[str, int] | None = None


@dataclass
class StreamChunk:
    delta: Message
    index: int
    finish_reason: str | None = None


Api = str
Provider = str


@dataclass
class Model:
    id: str
    name: str
    api: Api
    provider: Provider
    base_url: str = ""
    reasoning: bool = False
    input: tuple[str, ...] = ("text",)
    cost: dict[str, float] = field(
        default_factory=lambda: {
            "input": 0.0,
            "output": 0.0,
            "cacheRead": 0.0,
            "cacheWrite": 0.0,
        }
    )
    context_window: int = 0
    max_tokens: int = 0
