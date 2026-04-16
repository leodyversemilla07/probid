"""AI-powered provider for probid agent runtime using LLM."""

from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from probid_ai import ChatCompletionRequest, Message, OpenAIClient
from probid_agent.types import ExecutionPlan, ToolTraceItem
from probid_probing_agent.core.model_resolver import resolve_default_model, resolve_default_temperature

if TYPE_CHECKING:
    from probid_agent.types import ProviderRuntimeProtocol


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

If unsure, use probe with the user's query.
"""


class AIModelProvider:
    """AI-powered provider using LLM to generate plans."""

    def __init__(
        self,
        model: str | None = None,
        temperature: float | None = None,
        client: OpenAIClient | None = None,
    ):
        self.model = model or resolve_default_model()
        self.temperature = (
            resolve_default_temperature() if temperature is None else temperature
        )
        self.client = client or OpenAIClient()
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
            return _error_response(runtime, user_input, "LLM response had no choices", llm_response="")

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
            runtime._validate_plan(plan)
        except json.JSONDecodeError as e:
            return _error_response(runtime, user_input, f"Failed to parse LLM response: {e}", llm_content)
        except ValueError as e:
            return _error_response(runtime, user_input, str(e), llm_content)

        from probid_agent.proxy import execute_plan_steps
        from probid_probing_agent.core.tools import build_tool_registry
        from probid_probing_agent.core.data import cache

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


def handle_ai(user_input: str, runtime: "ProviderRuntimeProtocol") -> dict[str, Any]:
    """AI provider handler function."""
    provider = AIModelProvider()
    return provider.handle(user_input, runtime)
