"""AI-powered provider for probid agent runtime using LLM."""

from __future__ import annotations

import json
import os
import re
from typing import TYPE_CHECKING, Any, Union

from probid_ai import ChatCompletionRequest, Message
from probid_ai.openai_client import OpenAIClient
from probid_ai.anthropic_client import AnthropicClient
from probid_agent.proxy import execute_plan_steps
from probid_agent.types import ExecutionPlan, ToolTraceItem
from probid_probing_agent.core.data import cache
from probid_probing_agent.core.model_resolver import resolve_default_model, resolve_default_temperature
from probid_probing_agent.core.planner import normalize_plan, supported_tools
from probid_probing_agent.core.tools import build_tool_registry

# Models that use Anthropic-compatible API (via OpenCode Zen)
ANTHROPIC_COMPATIBLE_MODELS = {
    "minimax-m2.5-free",
    "minimax-m2.5",
    "minimax-m2",
    "minimax-m2.1",
    "big-pickle",
}

if TYPE_CHECKING:
    from probid_agent.types import ProviderRuntimeProtocol


def _get_client_for_model(model: str) -> Union[OpenAIClient, AnthropicClient]:
    """Get the appropriate client for a model."""
    model_lower = model.lower().strip()
    
    # Check if model uses Anthropic-compatible API
    if model_lower in ANTHROPIC_COMPATIBLE_MODELS:
        # Use Anthropic client with OpenCode Zen base URL
        base_url = os.environ.get("OPENCODE_BASE_URL", "https://opencode.ai/zen")
        return AnthropicClient(base_url=base_url, provider_name="opencode")
    
    # Default to OpenAI client
    base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
    return OpenAIClient(base_url=base_url, provider_name="openai")


def _build_system_prompt() -> str:
    return """You are a procurement analysis agent for Philippine government contracts.

You help users probe PhilGEPS procurement data for:
- Risk detection (overpricing, repeat awardees, contract splitting)
- Agency and supplier profiling
- Notice search and detail lookup

Available tools map to CLI commands:
- probid probe "<query>" --pages N --min-confidence level --max-findings N
- probid search "<keyword>" --pages N --detail
- probid detail <ref_id>
- probid awards --agency <name> --supplier <name>
- probid supplier "<name>"
- probid agency "<name>"
- probid repeat --min-count N
- probid split "<agency>" --gap-days N
- probid overprice "<keyword>" --threshold N

Always respond with a valid JSON plan containing:
- intent: the operation type (probe, search, awards, detail, repeat, split, overprice, supplier, agency)
- query: the user's search term
- steps: array of tool calls with tool name, args, and cli_equivalent

Rules:
- Use only these tools: probe, search, detail, awards, supplier, agency, repeat, split, network, overprice.
- Prefer multi-step investigative plans when the user asks to probe an agency or supplier.
- End investigative plans with the most decision-useful step, usually probe, supplier, agency, network, or overprice.
- Keep every step consistent with an actual probid CLI command.

If unsure, use probe with the user's query.
"""


class AIModelProvider:
    """AI-powered provider using LLM to generate plans."""

    def __init__(
        self,
        model: str | None = None,
        temperature: float | None = None,
        client: Union[OpenAIClient, AnthropicClient] | None = None,
    ):
        self.model = model or resolve_default_model()
        self.temperature = (
            resolve_default_temperature() if temperature is None else temperature
        )
        # Auto-select client based on model if not provided
        self.client = client or _get_client_for_model(self.model)
        self.system_prompt = _build_system_prompt()

    def handle(self, user_input: str, runtime: "ProviderRuntimeProtocol") -> dict[str, Any]:
        """Handle user input by generating a plan via LLM."""
        messages = [
            Message(role="system", content=self.system_prompt),
            Message(role="user", content=user_input),
        ]

        request = ChatCompletionRequest(
            model=self.model,
            messages=messages,
            temperature=self.temperature,
        )

        response = self.client.chat_completions(request)
        if not response.choices:
            raise ValueError("LLM response had no choices")

        llm_content = response.choices[0].message.content

        try:
            plan = _parse_plan_json(llm_content)
            if not isinstance(plan, dict):
                raise ValueError("Plan must be a dictionary")
            if "intent" not in plan:
                raise ValueError("Plan must have 'intent' field")
            if "steps" not in plan:
                raise ValueError("Plan must have 'steps' field")
            if not isinstance(plan.get("steps"), list):
                raise ValueError("Plan 'steps' must be a list")
            plan = normalize_plan(plan)
            runtime._validate_plan(plan)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Failed to parse LLM response: {exc}") from exc

        with cache.connection(db_path=runtime.db_path) as conn:
            registry = build_tool_registry(conn)
            payload, tool_trace = execute_plan_steps(plan, registry, event_sink=runtime.session._emit)

        envelope = runtime._compose_response(plan=plan, payload=payload, tool_trace=tool_trace)
        envelope["llm_response"] = llm_content
        return envelope


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.IGNORECASE | re.DOTALL)


def _error_response(
    runtime: "ProviderRuntimeProtocol",
    user_input: str,
    error: str,
    llm_response: str,
) -> dict[str, Any]:
    plan: ExecutionPlan = {"intent": "error", "query": user_input, "steps": []}
    envelope = runtime._compose_response(plan=plan, payload=None, tool_trace=[])
    envelope["error"] = error
    envelope["llm_response"] = llm_response
    envelope.setdefault("caveats", []).append(error)
    return envelope


def _parse_plan_json(text: str) -> dict[str, Any]:
    raw = (text or "").strip()
    if not raw:
        raise json.JSONDecodeError("empty response", "", 0)

    candidates: list[str] = [raw]
    fenced = _JSON_FENCE_RE.findall(raw)
    candidates.extend(chunk.strip() for chunk in fenced if chunk.strip())

    decoder = json.JSONDecoder()
    for candidate in candidates:
        try:
            parsed = json.loads(candidate)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        for i, ch in enumerate(candidate):
            if ch != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(candidate[i:])
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                continue

    raise json.JSONDecodeError("no JSON object found", raw, 0)


def supported_ai_tools() -> list[str]:
    return sorted(supported_tools())


def handle_ai(user_input: str, runtime: "ProviderRuntimeProtocol") -> dict[str, Any]:
    """AI provider handler function."""
    provider = AIModelProvider()
    return provider.handle(user_input, runtime)
