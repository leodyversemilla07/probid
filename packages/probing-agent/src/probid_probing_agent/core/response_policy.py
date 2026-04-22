"""Domain response policy for procurement probing outputs."""

from __future__ import annotations

from typing import Any

from probid_agent.types import ResponseEnvelope


class ProcurementResponsePolicy:
    def assumptions(self) -> list[str]:
        return [
            "Analysis is based on local cache unless live scrape is explicitly executed.",
            "Findings are triage signals, not legal conclusions.",
        ]

    def enrich(self, envelope: ResponseEnvelope, context: dict[str, Any]) -> None:
        payload = context.get("payload")
        query = context.get("query", "")
        tool_trace = context.get("tool_trace", []) or []

        self._enrich_tool_trace(envelope, tool_trace)
        self._enrich_step_payloads(envelope, tool_trace)

        if isinstance(payload, dict):
            if "stats" in payload and "awards" in payload:
                self._enrich_profile_payload(envelope, payload, query=query, intent=context.get("intent", ""))
            elif {"category", "threshold", "results"}.issubset(payload.keys()):
                self._enrich_overprice_payload(envelope, payload, query=query)
            elif "competitors" in payload and "agencies_served" in payload:
                self._enrich_network_payload(envelope, payload)

    def _enrich_tool_trace(self, envelope: ResponseEnvelope, tool_trace: list[dict[str, Any]]) -> None:
        if not tool_trace:
            return

        executed = [step.get("tool", "") for step in tool_trace if step.get("tool")]
        if executed:
            envelope["evidence"].append(f"steps_executed={len(executed)}")
            envelope["evidence"].append(f"tools_executed={','.join(executed)}")

        failed = [step for step in tool_trace if step.get("status") == "error"]
        for step in failed:
            envelope["caveats"].append(
                f"Tool {step.get('tool', 'unknown')} failed: {step.get('error', 'unknown error')}"
            )

    def _enrich_step_payloads(self, envelope: ResponseEnvelope, tool_trace: list[dict[str, Any]]) -> None:
        for step in tool_trace:
            if step.get("status") != "success":
                continue
            tool = step.get("tool", "")
            payload = step.get("payload")

            if tool in {"awards", "search", "repeat", "split"} and isinstance(payload, list):
                envelope["evidence"].append(f"{tool}_rows={len(payload)}")
                if tool == "awards" and payload:
                    agencies = {row.get("agency", "") for row in payload if isinstance(row, dict) and row.get("agency")}
                    suppliers = {row.get("supplier", "") for row in payload if isinstance(row, dict) and row.get("supplier")}
                    if agencies:
                        envelope["evidence"].append(f"awards_agencies={len(agencies)}")
                    if suppliers:
                        envelope["evidence"].append(f"awards_suppliers={len(suppliers)}")

            if tool == "network" and isinstance(payload, dict):
                agencies_served = payload.get("agencies_served", []) or []
                competitors = payload.get("competitors", []) or []
                envelope["evidence"].append(f"network_agencies={len(agencies_served)}")
                envelope["evidence"].append(f"network_competitors={len(competitors)}")

            if tool == "detail" and isinstance(payload, dict) and payload:
                envelope["evidence"].append("detail_found=true")

    def _enrich_profile_payload(
        self,
        envelope: ResponseEnvelope,
        payload: dict[str, Any],
        *,
        query: str,
        intent: str,
    ) -> None:
        stats = payload.get("stats", {}) or {}
        awards = payload.get("awards", []) or []
        total_awards = int(stats.get("total_awards", 0) or 0)
        agency_count = int(stats.get("agency_count", 0) or 0)
        total_value = stats.get("total_value", 0) or 0

        envelope["evidence"].extend(
            [
                f"total_awards={total_awards}",
                f"agency_count={agency_count}",
                f"returned_awards={len(awards)}",
            ]
        )
        if total_value:
            envelope["evidence"].append(f"total_value={total_value}")

        if total_awards > 0:
            label = "supplier" if intent == "supplier" else "agency"
            envelope["findings"].append(
                {
                    "summary": f"{label.title()} profile for {query or label} shows {total_awards} cached awards across {agency_count} agencies.",
                    "evidence": {
                        "total_awards": total_awards,
                        "agency_count": agency_count,
                        "total_value": total_value,
                    },
                }
            )
        else:
            envelope["caveats"].append("No award history found in local cache for this profile.")

        if not envelope["next_actions"] and query:
            if intent == "supplier":
                envelope["next_actions"].extend(
                    [
                        f'probid network "{query}"',
                        f'probid awards --supplier "{query}"',
                    ]
                )
            elif intent == "agency":
                envelope["next_actions"].extend(
                    [
                        f'probid awards --agency "{query}"',
                        f'probid split "{query}" --gap-days 30',
                    ]
                )

    def _enrich_overprice_payload(
        self,
        envelope: ResponseEnvelope,
        payload: dict[str, Any],
        *,
        query: str,
    ) -> None:
        results = payload.get("results", []) or []
        threshold = payload.get("threshold", 200)
        category = payload.get("category", query)

        envelope["evidence"].append(f"overprice_result_count={len(results)}")
        envelope["evidence"].append(f"overprice_threshold_pct={threshold}")

        if results:
            top = results[0]
            envelope["findings"].append(
                {
                    "summary": (
                        f"Top budget-spread candidate for '{category}' is '{top.get('category', '')}' "
                        f"with {int(top.get('sample_count', 0) or 0)} samples."
                    ),
                    "evidence": {
                        "category": top.get("category", ""),
                        "sample_count": int(top.get("sample_count", 0) or 0),
                        "min_price": top.get("min_price", 0) or 0,
                        "max_price": top.get("max_price", 0) or 0,
                    },
                }
            )
        else:
            envelope["caveats"].append("No comparable cached categories met the current overpricing threshold.")

        if not envelope["next_actions"] and category:
            envelope["next_actions"].extend(
                [
                    f'probid probe "{category}" --why',
                    f'probid search "{category}" --detail',
                ]
            )

    def _enrich_network_payload(self, envelope: ResponseEnvelope, payload: dict[str, Any]) -> None:
        agencies_served = payload.get("agencies_served", []) or []
        competitors = payload.get("competitors", []) or []
        envelope["evidence"].append(f"agencies_served={len(agencies_served)}")
        envelope["evidence"].append(f"competitor_count={len(competitors)}")
        if competitors:
            top = competitors[0]
            envelope["findings"].append(
                {
                    "summary": (
                        f"Supplier overlaps with {len(competitors)} competitors; top shared competitor is "
                        f"{top.get('supplier', 'UNKNOWN')} across {top.get('shared_agencies', 0)} agencies."
                    )
                }
            )
        else:
            envelope["caveats"].append("No competitor overlap found in the current cached award data.")
