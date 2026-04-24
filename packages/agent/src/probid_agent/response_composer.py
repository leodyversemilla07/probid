"""Reusable response composition helpers for agent runtimes."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from probid_agent.types import DomainResponsePolicy, ResponseEnvelope, ToolTraceItem

EnvelopeEnricher = Callable[[ResponseEnvelope, dict[str, Any]], None]


class BaseResponseComposer:
    def default_assumptions(self) -> list[str]:
        return [
            "Results depend on available local/runtime data.",
            "Outputs are triage signals and should be verified with source records.",
        ]

    def compose(
        self,
        *,
        intent: str,
        query: str,
        payload: Any,
        tool_trace: list[ToolTraceItem],
        fallback_next_actions: Callable[[str], list[str]] | None = None,
        assumptions: list[str] | None = None,
        enricher: EnvelopeEnricher | None = None,
        policy: DomainResponsePolicy | None = None,
    ) -> ResponseEnvelope:
        assumptions = assumptions or (policy.assumptions() if policy is not None else self.default_assumptions())
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
            if not next_actions and fallback_next_actions is not None:
                next_actions.extend(fallback_next_actions(query))
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

        envelope: ResponseEnvelope = {
            "intent": intent,
            "query": query,
            "assumptions": assumptions,
            "evidence": evidence,
            "findings": findings,
            "caveats": caveats,
            "next_actions": next_actions,
            "tool_trace": tool_trace,
        }

        context = {
            "intent": intent,
            "query": query,
            "payload": payload,
            "tool_trace": tool_trace,
        }

        if policy is not None:
            policy.enrich(envelope, context)

        if enricher is not None:
            enricher(envelope, context)

        return envelope
