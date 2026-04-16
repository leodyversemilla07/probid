"""Messaging/bot integration package for probid."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Message:
    """A message in the messaging system."""

    role: str  # "user", "assistant", "system"
    content: str
    timestamp: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Conversation:
    """A conversation thread."""

    id: str
    messages: list[Message] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)

    def add_message(self, role: str, content: str, metadata: dict[str, Any] | None = None) -> Message:
        msg = Message(role=role, content=content, metadata=metadata or {})
        self.messages.append(msg)
        return msg


class BotStore:
    """Simple in-memory store for bot conversations."""

    def __init__(self):
        self.conversations: dict[str, Conversation] = {}

    def get_conversation(self, conv_id: str) -> Conversation | None:
        return self.conversations.get(conv_id)

    def create_conversation(self, conv_id: str) -> Conversation:
        conv = Conversation(id=conv_id)
        self.conversations[conv_id] = conv
        return conv

    def list_conversations(self) -> list[str]:
        return list(self.conversations.keys())

    def delete_conversation(self, conv_id: str) -> bool:
        if conv_id in self.conversations:
            del self.conversations[conv_id]
            return True
        return False


# Global store instance
_store: BotStore | None = None


def get_store() -> BotStore:
    """Get the global bot store instance."""
    global _store
    if _store is None:
        _store = BotStore()
    return _store


__all__ = [
    "Message",
    "Conversation",
    "BotStore",
    "get_store",
]
