"""Model/provider resolution helpers for the probing agent."""

from __future__ import annotations

import os


def resolve_default_model() -> str:
    return (
        os.environ.get("PROBID_AI_MODEL")
        or os.environ.get("OPENAI_MODEL")
        or "gpt-4"
    )


def resolve_default_temperature(default: float = 0.7) -> float:
    raw = os.environ.get("PROBID_AI_TEMPERATURE")
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    if value < 0 or value > 2:
        return default
    return value
