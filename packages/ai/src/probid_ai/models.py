"""Minimal model registry and helpers."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from probid_ai.types import Model

_MODELS: dict[str, dict[str, Model]] = {
    "anthropic": {
        "claude-opus-4-6": Model(
            id="claude-opus-4-6",
            name="Claude Opus 4.6",
            api="anthropic-messages",
            provider="anthropic",
            reasoning=True,
            context_window=200000,
            max_tokens=32000,
            cost={"input": 15.0, "output": 75.0, "cacheRead": 0.3, "cacheWrite": 3.75},
        ),
        "claude-sonnet-4-5": Model(
            id="claude-sonnet-4-5",
            name="Claude Sonnet 4.5",
            api="anthropic-messages",
            provider="anthropic",
            reasoning=True,
            context_window=200000,
            max_tokens=32000,
            cost={"input": 3.0, "output": 15.0, "cacheRead": 0.06, "cacheWrite": 0.75},
        ),
    },
    "openai-codex": {
        "gpt-5.4": Model(
            id="gpt-5.4",
            name="GPT-5.4",
            api="openai-responses",
            provider="openai-codex",
            reasoning=True,
            context_window=200000,
            max_tokens=32000,
            cost={"input": 5.0, "output": 15.0, "cacheRead": 0.5, "cacheWrite": 2.5},
        ),
        "gpt-5.3-codex": Model(
            id="gpt-5.3-codex",
            name="GPT-5.3-Codex",
            api="openai-responses",
            provider="openai-codex",
            reasoning=True,
            context_window=200000,
            max_tokens=32000,
            cost={"input": 5.0, "output": 15.0, "cacheRead": 0.5, "cacheWrite": 2.5},
        ),
    },
    "openrouter": {
        "anthropic/claude-opus-4.6": Model(
            id="anthropic/claude-opus-4.6",
            name="OpenRouter Claude Opus 4.6",
            api="openai-completions",
            provider="openrouter",
            reasoning=True,
            context_window=200000,
            max_tokens=32000,
            cost={"input": 15.0, "output": 75.0, "cacheRead": 0.3, "cacheWrite": 3.75},
        )
    },
    "openai": {
        "gpt-4": Model(
            id="gpt-4",
            name="GPT-4",
            api="openai-responses",
            provider="openai",
            reasoning=False,
            context_window=128000,
            max_tokens=4096,
            cost={"input": 30.0, "output": 60.0, "cacheRead": 0.0, "cacheWrite": 0.0},
        )
    },
}


def get_model(provider: str, model_id: str) -> Model | None:
    model = _MODELS.get(provider, {}).get(model_id)
    return deepcopy(model) if model is not None else None


def get_providers() -> list[str]:
    return list(_MODELS.keys())


def get_models(provider: str) -> list[Model]:
    return [deepcopy(model) for model in _MODELS.get(provider, {}).values()]


def calculate_cost(model: Model, usage: dict[str, Any]) -> dict[str, float]:
    input_tokens = float(usage.get("input", 0) or 0)
    output_tokens = float(usage.get("output", 0) or 0)
    cache_read_tokens = float(usage.get("cacheRead", 0) or 0)
    cache_write_tokens = float(usage.get("cacheWrite", 0) or 0)

    cost = {
        "input": (model.cost.get("input", 0.0) / 1_000_000) * input_tokens,
        "output": (model.cost.get("output", 0.0) / 1_000_000) * output_tokens,
        "cacheRead": (model.cost.get("cacheRead", 0.0) / 1_000_000) * cache_read_tokens,
        "cacheWrite": (model.cost.get("cacheWrite", 0.0) / 1_000_000) * cache_write_tokens,
        "total": 0.0,
    }
    cost["total"] = cost["input"] + cost["output"] + cost["cacheRead"] + cost["cacheWrite"]
    usage["cost"] = cost
    return cost


def supports_xhigh(model: Model) -> bool:
    model_id = model.id.lower()
    if "gpt-5.2" in model_id or "gpt-5.3" in model_id or "gpt-5.4" in model_id:
        return True
    if "opus-4-6" in model_id or "opus-4.6" in model_id:
        return True
    return False


def models_are_equal(a: Model | None, b: Model | None) -> bool:
    if a is None or b is None:
        return False
    return a.id == b.id and a.provider == b.provider


# pi-style aliases
getModel = get_model
getProviders = get_providers
getModels = get_models
calculateCost = calculate_cost
supportsXhigh = supports_xhigh
modelsAreEqual = models_are_equal
