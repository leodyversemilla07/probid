"""Reusable tool-calling primitives for probid agent core."""

from __future__ import annotations

from typing import Any

from probid_agent.types import EventSink, ToolSpec


class ToolRegistry:
    def __init__(self, specs: list[ToolSpec]):
        self._specs = {spec.name: spec for spec in specs}

    def get(self, name: str) -> ToolSpec:
        spec = self._specs.get(name)
        if spec is None:
            available = ", ".join(sorted(self._specs)) or "none"
            raise ValueError(f"Unknown tool '{name}'. Available tools: {available}")
        return spec

    def list_specs(self) -> list[ToolSpec]:
        return [self._specs[name] for name in sorted(self._specs)]

    def execute(
        self,
        name: str,
        args: dict[str, Any],
        *,
        cli_equivalent: str = "",
        event_sink: EventSink | None = None,
    ) -> tuple[Any, dict[str, Any]]:
        spec = self.get(name)
        if event_sink is not None:
            event_sink(
                {
                    "type": "tool_execution_start",
                    "tool": spec.name,
                    "args": args,
                    "cli_equivalent": cli_equivalent,
                }
            )

        try:
            payload = spec.handler(**args)
            trace = {
                "tool": spec.name,
                "description": spec.description,
                "args": args,
                "cli_equivalent": cli_equivalent,
                "status": "success",
                "result_type": type(payload).__name__,
                "payload": payload,
            }
            if event_sink is not None:
                event_sink(
                    {
                        "type": "tool_execution_end",
                        "tool": spec.name,
                        "args": args,
                        "cli_equivalent": cli_equivalent,
                        "status": "success",
                        "result_type": trace["result_type"],
                    }
                )
            return payload, trace
        except Exception as exc:
            trace = {
                "tool": spec.name,
                "description": spec.description,
                "args": args,
                "cli_equivalent": cli_equivalent,
                "status": "error",
                "error": str(exc),
                "result_type": "error",
            }
            if event_sink is not None:
                event_sink(
                    {
                        "type": "tool_execution_end",
                        "tool": spec.name,
                        "args": args,
                        "cli_equivalent": cli_equivalent,
                        "status": "error",
                        "error": str(exc),
                    }
                )
            raise
