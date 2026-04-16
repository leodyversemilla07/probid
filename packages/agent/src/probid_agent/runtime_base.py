"""Base runtime helpers for agent implementations."""

from __future__ import annotations

from typing import Any

from probid_agent.proxy import validate_plan_contract
from probid_agent.types import ExecutionPlan, ResponseEnvelope, ToolTraceItem


class BaseAgentRuntime:
    """Provider-agnostic runtime helpers.

    Concrete runtimes can extend this to share plan validation and response-envelope
    boilerplate while keeping domain-specific composition logic in package-local code.
    """

    def validate_plan(self, plan: ExecutionPlan) -> None:
        validate_plan_contract(plan)

    def default_assumptions(self) -> list[str]:
        return [
            "Analysis is based on local cache unless live scrape is explicitly executed.",
            "Findings are triage signals, not legal conclusions.",
        ]

    def build_response_envelope(
        self,
        *,
        intent: str,
        query: str,
        assumptions: list[str] | None = None,
        evidence: list[str] | None = None,
        findings: list[dict[str, Any]] | None = None,
        caveats: list[str] | None = None,
        next_actions: list[str] | None = None,
        tool_trace: list[ToolTraceItem] | None = None,
    ) -> ResponseEnvelope:
        return {
            "intent": intent,
            "query": query,
            "assumptions": assumptions or [],
            "evidence": evidence or [],
            "findings": findings or [],
            "caveats": caveats or [],
            "next_actions": next_actions or [],
            "tool_trace": tool_trace or [],
        }
