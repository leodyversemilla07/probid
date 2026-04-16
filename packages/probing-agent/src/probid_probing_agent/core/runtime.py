"""Runtime orchestrator for the probid terminal probing agent harness."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from probid_agent.runtime_base import BaseAgentRuntime
from probid_agent.runtime_lifecycle import open_or_create_session, persist_turn
from probid_agent.types import ExecutionPlan, ToolTraceItem
from probid_probing_agent.core import providers  # noqa: F401  # ensure built-in providers register
from probid_probing_agent.core.prompt import get_system_prompt
from probid_probing_agent.core.provider_registry import get_provider, list_providers
from probid_probing_agent.core.response_builder import ResponseBuilder
from probid_probing_agent.core.session import AgentSessionLogger, ProbidAgentSession
from probid_probing_agent.core.session_manager import ProbidSessionManager


class ProbidAgentRuntime(BaseAgentRuntime):
    def __init__(
        self,
        db_path: str | None = None,
        default_cache_only: bool = True,
        provider: str = "deterministic",
        session_dir: str | None = None,
        continue_recent: bool = False,
    ):
        self.db_path = db_path
        self.default_cache_only = default_cache_only
        self.system_prompt = get_system_prompt()
        self._response_builder = ResponseBuilder()
        self.session_manager = ProbidSessionManager(Path(session_dir) if session_dir else None)

        enable_session_logging = os.environ.get("PROBID_AGENT_LOG_SESSION", "0").strip().lower()
        if enable_session_logging in {"1", "true", "yes", "on"}:
            self.session_logger = AgentSessionLogger()
        else:
            self.session_logger = None

        selected = get_provider(provider)
        if selected is None:
            available = ", ".join(list_providers()) or "none"
            raise ValueError(f"Unknown provider '{provider}'. Available providers: {available}")

        self.provider_name = provider
        self.provider = selected
        self.session = self._open_session(continue_recent=continue_recent)

    def available_tools(self) -> list[str]:
        return [
            "probid probe \"<query>\" --pages 1 --min-confidence low --max-findings 5",
            "probid detail <ref_id>",
            "probid awards",
            "probid supplier \"<name>\"",
            "probid agency \"<name>\"",
            "probid repeat --min-count 3",
            "probid split \"<agency>\" --gap-days 30",
        ]

    def _validate_plan(self, plan: ExecutionPlan) -> None:
        self.validate_plan(plan)

    def _open_session(self, continue_recent: bool = False) -> ProbidAgentSession:
        return open_or_create_session(
            continue_recent=continue_recent,
            session_manager=self.session_manager,
            system_prompt=self.system_prompt,
            session_factory=ProbidAgentSession,
        )

    def new_session(self) -> ProbidAgentSession:
        self.session = self._open_session(continue_recent=False)
        return self.session

    def handle_input(self, user_input: str) -> dict[str, Any]:
        response = self.session.prompt(user_input, self)
        response["provider"] = self.provider_name

        persist_turn(
            session_manager=self.session_manager,
            session_id=self.session.session_id,
            user_input=user_input,
            response=response,
        )

        if self.session_logger is not None:
            logged_turn_id = self.session_logger.log_turn(
                user_input=user_input,
                result=response,
                turn_id=response.get("turn_id"),
            )
            response["turn_id"] = logged_turn_id

        return response

    def _compose_response(
        self,
        plan: ExecutionPlan,
        payload: Any,
        tool_trace: list[ToolTraceItem],
    ) -> dict[str, Any]:
        intent = plan.get("intent", "unknown")
        query = plan.get("query", "")
        return self._response_builder.build(
            intent=intent,
            query=query,
            payload=payload,
            tool_trace=tool_trace,
            fallback_next_actions=lambda q: [
                f"probid probe \"{q}\" --why",
                f"probid probe \"{q}\" --json",
                f"probid search \"{q}\" --detail",
            ],
        )
