"""Reusable provider execution runner for agent runtimes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from probid_agent.types import (
    ExecutionPlan,
    ProviderRuntimeProtocol,
    ResponseEnvelope,
    ToolTraceItem,
)

PlanBuilder = Callable[[str], ExecutionPlan]
PlanExecutor = Callable[[ProviderRuntimeProtocol, ExecutionPlan], tuple[Any, list[ToolTraceItem]]]


class BaseProviderRunner:
    """Executes plan lifecycle for provider handlers.

    Runtime contract expected:
    - `_validate_plan(plan)`
    - `_compose_response(plan, payload, tool_trace)`
    """

    def execute(
        self,
        *,
        user_input: str,
        runtime: ProviderRuntimeProtocol,
        build_plan: PlanBuilder,
        execute_plan: PlanExecutor,
    ) -> ResponseEnvelope:
        plan = build_plan(user_input)
        runtime._validate_plan(plan)
        payload, tool_trace = execute_plan(runtime, plan)
        return runtime._compose_response(plan=plan, payload=payload, tool_trace=tool_trace)


class DeterministicProviderAdapter:
    """Small reusable adapter for deterministic plan->tools->response providers."""

    def __init__(
        self,
        *,
        build_plan: PlanBuilder,
        execute_plan: PlanExecutor,
        runner: BaseProviderRunner | None = None,
    ):
        self._build_plan = build_plan
        self._execute_plan = execute_plan
        self._runner = runner or BaseProviderRunner()

    def handle(self, user_input: str, runtime: ProviderRuntimeProtocol) -> ResponseEnvelope:
        return self._runner.execute(
            user_input=user_input,
            runtime=runtime,
            build_plan=self._build_plan,
            execute_plan=self._execute_plan,
        )
