"""Response handling helpers for probing-agent runtime."""

from __future__ import annotations

from typing import Any, Callable

from probid_agent.response_composer import BaseResponseComposer
from probid_agent.types import ResponseEnvelope, ToolTraceItem

from probid_probing_agent.core.response_policy import ProcurementResponsePolicy


class ResponseBuilder:
    """Builds ResponseEnvelope objects for probing intents."""

    def __init__(self):
        self._composer = BaseResponseComposer()
        self._policy = ProcurementResponsePolicy()

    def build(
        self,
        *,
        intent: str,
        query: str,
        payload: Any,
        tool_trace: list[ToolTraceItem],
        fallback_next_actions: Callable[[str], list[str]] | None = None,
    ) -> ResponseEnvelope:
        return self._composer.compose(
            intent=intent,
            query=query,
            payload=payload,
            tool_trace=tool_trace,
            policy=self._policy,
            fallback_next_actions=fallback_next_actions,
        )
