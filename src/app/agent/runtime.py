"""Runtime orchestrator for probid terminal agent."""

from __future__ import annotations

import os
from typing import Any

from app.agent import providers  # noqa: F401  # ensure built-in providers register
from app.agent.prompt import get_system_prompt
from app.agent.provider_registry import get_provider, list_providers
from app.agent.session import AgentSessionLogger


class ProbidAgentRuntime:
    def __init__(
        self,
        db_path: str | None = None,
        default_cache_only: bool = True,
        provider: str = "deterministic",
    ):
        self.db_path = db_path
        self.default_cache_only = default_cache_only
        self.system_prompt = get_system_prompt()

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

    def _validate_plan(self, plan: dict[str, Any]) -> None:
        for idx, step in enumerate(plan.get("steps", []), start=1):
            if not step.get("tool"):
                raise ValueError(f"Invalid plan step {idx}: missing tool")
            if not step.get("cli_equivalent"):
                raise ValueError(f"Invalid plan step {idx}: missing cli_equivalent")

    def handle_input(self, user_input: str) -> dict[str, Any]:
        response = self.provider.handle(user_input, self)
        response["provider"] = self.provider_name

        if self.session_logger is not None:
            turn_id = self.session_logger.log_turn(user_input=user_input, result=response)
            response["turn_id"] = turn_id

        return response

    def _compose_response(
        self,
        plan: dict[str, Any],
        payload: Any,
        tool_trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        intent = plan.get("intent", "unknown")
        query = plan.get("query", "")

        assumptions = [
            "Analysis is based on local cache unless live scrape is explicitly executed.",
            "Findings are triage signals, not legal conclusions.",
        ]

        evidence: list[str] = []
        findings: list[dict[str, Any]] = []
        caveats: list[str] = []
        next_actions: list[str] = []

        if intent == "probe" and isinstance(payload, dict):
            summary = payload.get("summary", {})
            findings = payload.get("findings", [])
            evidence.append(f"records_scanned={summary.get('records_scanned', 0)}")
            evidence.append(f"agencies_touched={summary.get('agencies_touched', 0)}")
            caveat_note = summary.get("data_quality_note")
            if caveat_note:
                caveats.append(caveat_note)
            next_actions.extend(payload.get("next_checks", []))
            if not next_actions:
                next_actions.extend(
                    [
                        f"probid probe \"{query}\" --why",
                        f"probid probe \"{query}\" --json",
                        f"probid search \"{query}\" --detail",
                    ]
                )
        elif intent in {"search", "awards", "repeat", "split"} and isinstance(payload, list):
            evidence.append(f"result_count={len(payload)}")
            if payload:
                findings.append({"summary": f"Returned {len(payload)} row(s)"})
            else:
                caveats.append("No matching rows in local cache.")
        elif intent in {"detail", "supplier", "agency"}:
            if payload:
                evidence.append("entity_found=true")
                findings.append({"summary": f"{intent} record found"})
            else:
                caveats.append("Requested record not found in local cache.")

        response = {
            "intent": intent,
            "query": query,
            "assumptions": assumptions,
            "evidence": evidence,
            "findings": findings,
            "caveats": caveats,
            "next_actions": next_actions,
            "tool_trace": tool_trace,
        }
        return response
