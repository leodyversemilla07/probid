"""Session state and logging for the probid probing agent harness."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from probid_agent.agent_loop import BaseAgentSession
from probid_agent.session_logger import JsonlTurnLogger


_REEXPORT_FORMAT_ALIASES: dict[str, set[str]] = {
    "json": {"re-export the last json export", "re-export last json export", "re-export the last json artifact"},
    "markdown": {"re-export the last markdown report", "re-export last markdown report", "re-export the last markdown export"},
    "csv": {"re-export the last csv summary", "re-export last csv summary", "re-export the last csv export"},
    "timeline": {"re-export the last case timeline", "re-export last case timeline"},
    "findings_table": {"re-export the last findings table", "re-export last findings table"},
    "handoff": {"re-export the last handoff note", "re-export last handoff note", "re-export the last analyst handoff"},
    "case_summary": {"re-export the last case summary", "re-export last case summary"},
}


class ProbidAgentSession(BaseAgentSession):
    """Minimal in-memory session state for the probing harness.

    This is intentionally small: it tracks message history, turn IDs, tool traces,
    queue placeholders, and lightweight event subscribers so the runtime can evolve
    toward fuller tool-calling/state-management behavior without a rewrite.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.investigation_context: dict[str, str] = {}
        self.export_artifacts: list[dict[str, Any]] = []
        self.restore_from_messages()

    def restore_from_messages(self) -> None:
        """Rebuild lightweight investigation memory from persisted assistant turns."""
        context: dict[str, str] = {}
        tool_trace: list[dict[str, Any]] = []
        for message in self.messages:
            if message.get("role") != "assistant":
                continue
            content = message.get("content")
            if not isinstance(content, dict):
                continue
            context = self._update_investigation_context(context, content)
            trace = content.get("tool_trace", []) or []
            if isinstance(trace, list):
                tool_trace = list(trace)
        self.investigation_context = context
        self.tool_trace = tool_trace

    def restore_from_rows(self, rows: list[dict[str, Any]]) -> None:
        """Rebuild investigation memory plus export metadata from persisted rows."""
        self.restore_from_messages()
        self.export_artifacts = []
        context = dict(self.investigation_context)
        for row in rows:
            if row.get("type") != "export_artifact":
                continue
            self.export_artifacts.append(dict(row))
            context = self._update_export_context(context, row)
        self.investigation_context = context

    def prompt(self, user_input: str, runtime: Any) -> dict[str, Any]:
        turn_id = self.new_turn_id()
        steering = self._drain_steering()
        follow_up = self._drain_follow_up()
        self._emit_queue_update()

        working_context = dict(self.investigation_context)
        for item in steering:
            working_context.update(self._parse_context_hint(item))

        effective_input = user_input
        context_block = self._format_context_block(working_context)
        if context_block:
            effective_input = context_block + "\n\n" + effective_input
        if steering:
            effective_input = effective_input + "\n\n[Queued steering]\n" + "\n".join(f"- {item}" for item in steering)
        if follow_up:
            effective_input = effective_input + "\n\n[Queued follow-up]\n" + "\n".join(
                f"- {item}" for item in follow_up
            )

        self.is_streaming = True
        self.messages.append({"role": "user", "content": user_input, "turn_id": turn_id})
        self._emit(
            {
                "type": "turn_start",
                "turn_id": turn_id,
                "user_input": user_input,
                "queued_steering": steering,
                "queued_follow_up": follow_up,
            }
        )

        response = self._maybe_handle_explanatory_followup(user_input, working_context)
        try:
            if response is None:
                response = runtime.provider.handle(effective_input, runtime)
        finally:
            self.is_streaming = False

        self.tool_trace = list(response.get("tool_trace", []))
        self.investigation_context = self._update_investigation_context(working_context, response)
        self.messages.append(
            {
                "role": "assistant",
                "content": response,
                "turn_id": turn_id,
            }
        )
        response["turn_id"] = turn_id
        response["session_id"] = self.session_id
        response["state"] = self.snapshot_state()
        response["queue_applied"] = {
            "steering": steering,
            "follow_up": follow_up,
        }
        response["investigation_context"] = dict(self.investigation_context)
        self._emit(
            {
                "type": "turn_end",
                "turn_id": turn_id,
                "response": response,
                "tool_trace": self.tool_trace,
            }
        )
        return response

    def _split_context_items(self, value: str, limit: int | None = None) -> list[str]:
        items = [item for item in (value or "").split(" || ") if item]
        return items[:limit] if limit is not None else items

    def _summary_findings(self, *lines: str) -> list[dict[str, str]]:
        return [{"summary": line} for line in lines if line]

    def _explain_response(
        self,
        *,
        query: str,
        assumption: str | list[str],
        evidence: list[str] | None = None,
        findings: list[dict[str, Any]] | None = None,
        caveats: list[str] | None = None,
        next_actions: list[str] | None = None,
        export: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        assumptions = [assumption] if isinstance(assumption, str) else list(assumption)
        response = {
            "intent": "explain",
            "query": query,
            "assumptions": assumptions,
            "evidence": evidence or [],
            "findings": findings or [],
            "caveats": caveats or [],
            "next_actions": next_actions or [],
            "tool_trace": [],
        }
        if export is not None:
            response["export"] = export
        return response

    def _export_followup_response(
        self,
        *,
        query: str,
        assumption: str,
        evidence: list[str],
        findings_lines: list[str],
        caveats: list[str],
        next_actions: list[str],
        export_format: str,
        export_content: Any,
    ) -> dict[str, Any]:
        return self._explain_response(
            query=query,
            assumption=assumption,
            evidence=evidence,
            findings=self._summary_findings(*findings_lines),
            caveats=caveats,
            next_actions=next_actions,
            export={"format": export_format, "content": export_content},
        )

    def _audit_followup_response(
        self,
        *,
        query: str,
        assumption: str,
        findings_lines: list[str],
        export: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._explain_response(
            query=query,
            assumption=assumption,
            findings=self._summary_findings(*findings_lines),
            next_actions=[],
            export=export,
        )

    def _update_export_context(self, base_context: dict[str, str], artifact: dict[str, Any]) -> dict[str, str]:
        context = {k: v for k, v in base_context.items() if v}
        export_format = str(artifact.get("export_format", "")).strip()
        output_path = str(artifact.get("output_path", "")).strip()
        destination = str(artifact.get("destination", "")).strip()
        query = str(artifact.get("query", "")).strip()
        if export_format:
            context["last_export_format"] = export_format
        if output_path:
            context["last_export_path"] = output_path
        if destination:
            context["last_export_destination"] = destination
        if query:
            context["last_export_query"] = query
        recent = list(self.export_artifacts[-5:])
        if recent:
            labels = []
            for item in recent:
                fmt = str(item.get("export_format", "unknown")).strip() or "unknown"
                dest = str(item.get("destination", "stdout")).strip() or "stdout"
                path = str(item.get("output_path", "")).strip()
                labels.append(f"{fmt}:{path or dest}")
            context["recent_exports"] = " || ".join(labels)
        return context

    def remember_export_artifact(self, artifact: dict[str, Any]) -> None:
        self.export_artifacts.append(dict(artifact))
        self.investigation_context = self._update_export_context(self.investigation_context, artifact)

    def _followup_memory(self, context: dict[str, str]) -> dict[str, Any]:
        query = context.get("query", "")
        top_summary = context.get("top_finding_summary", "")
        second_summary = context.get("second_finding_summary", "")
        top_evidence = context.get("top_finding_evidence", "")
        last_caveats = context.get("last_caveats", "")
        last_evidence = context.get("last_evidence", "")
        last_next_actions = context.get("last_next_actions", "")
        return {
            "query": query,
            "top_summary": top_summary,
            "second_summary": second_summary,
            "top_evidence": top_evidence,
            "last_caveats": last_caveats,
            "last_evidence": last_evidence,
            "last_next_actions": last_next_actions,
            "top_evidence_items": self._split_context_items(top_evidence),
            "evidence_items": self._split_context_items(last_evidence),
            "caveat_items": self._split_context_items(last_caveats),
            "next_items": self._split_context_items(last_next_actions),
            "top_ref_id": context.get("top_ref_id", ""),
            "last_export_format": context.get("last_export_format", ""),
            "last_export_path": context.get("last_export_path", ""),
            "last_export_destination": context.get("last_export_destination", ""),
            "recent_exports": self._split_context_items(context.get("recent_exports", "")),
            "last_export_artifact": dict(self.export_artifacts[-1]) if self.export_artifacts else None,
        }

    def _prompt_is(self, prompt: str, *variants: str) -> bool:
        return prompt in set(variants)

    def _handle_explanation_followup(self, prompt: str, memory: dict[str, Any]) -> dict[str, Any] | None:
        query = memory["query"]
        top_summary = memory["top_summary"]
        second_summary = memory["second_summary"]
        top_evidence = memory["top_evidence"]
        last_caveats = memory["last_caveats"]
        last_evidence = memory["last_evidence"]
        last_next_actions = memory["last_next_actions"]
        top_evidence_items = memory["top_evidence_items"]
        evidence_items = memory["evidence_items"]
        caveat_items = memory["caveat_items"]
        next_items = memory["next_items"]
        top_ref_id = memory["top_ref_id"]

        if self._prompt_is(prompt, "explain the top finding", "explain top finding", "what does the top finding mean?") and top_summary:
            return self._explain_response(
                query=query,
                assumption=[
                    "Explanation is based on the last completed investigation turn.",
                    "This summarizes heuristics, not legal conclusions.",
                ],
                evidence=top_evidence_items,
                findings=self._summary_findings(top_summary),
                caveats=caveat_items,
                next_actions=[f'probid probe "{query}" --why' if query else 'probid probe "<query>" --why'],
            )

        if self._prompt_is(prompt, "what evidence supports that?", "what evidence supports the top finding?") and (top_evidence or last_evidence):
            return self._explain_response(
                query=query,
                assumption="Evidence is replayed from the last completed investigation turn.",
                evidence=top_evidence_items or evidence_items,
                findings=self._summary_findings(top_summary),
                caveats=caveat_items,
                next_actions=[f"probid detail {top_ref_id}"] if top_ref_id else [],
            )

        if self._prompt_is(prompt, "what are the caveats?", "what caveats apply?") and last_caveats:
            return self._explain_response(
                query=query,
                assumption="Caveats are replayed from the last completed investigation turn.",
                evidence=evidence_items,
                findings=self._summary_findings(top_summary),
                caveats=caveat_items,
                next_actions=[f'probid probe "{query}" --min-confidence high'] if query else [],
            )

        if self._prompt_is(prompt, "summarize the last result simply", "summarize the last result", "summarize simply") and (top_summary or last_evidence):
            simple = top_summary or "Last result summarized from the prior investigation turn."
            return self._explain_response(
                query=query,
                assumption="Plain-language summary is derived from the last completed investigation turn.",
                evidence=evidence_items[:3],
                findings=self._summary_findings(simple),
                caveats=caveat_items,
                next_actions=[f'probid probe "{query}" --why'] if query else [],
            )

        if self._prompt_is(prompt, "compare the top two findings", "compare top two findings") and top_summary and second_summary:
            return self._explain_response(
                query=query,
                assumption="Comparison is based on the ranked findings from the last investigation turn.",
                evidence=top_evidence_items or evidence_items[:3],
                findings=self._summary_findings(f"Top finding: {top_summary}", f"Second finding: {second_summary}"),
                caveats=caveat_items,
                next_actions=next_items[:2],
            )

        if self._prompt_is(prompt, "show only the caveats for the top finding", "top finding caveats") and last_caveats:
            return self._explain_response(
                query=query,
                assumption="Caveats reflect the last completed investigation turn.",
                evidence=[],
                findings=self._summary_findings(top_summary),
                caveats=caveat_items,
                next_actions=next_items[:1],
            )

        if self._prompt_is(prompt, "which finding is strongest?", "which finding is strongest", "strongest finding?") and top_summary:
            return self._explain_response(
                query=query,
                assumption="Strength follows the current ranking in the last investigation turn.",
                evidence=top_evidence_items,
                findings=self._summary_findings(f"Strongest current finding: {top_summary}"),
                caveats=caveat_items[:2],
                next_actions=next_items[:1],
            )

        if self._prompt_is(prompt, "what should i check next?", "what should i check next", "next checks?") and last_next_actions:
            return self._explain_response(
                query=query,
                assumption="Next checks are replayed from the prior investigation turn.",
                evidence=evidence_items[:2],
                findings=self._summary_findings(top_summary),
                caveats=caveat_items[:2],
                next_actions=next_items,
            )

        return None

    def _handle_style_followup(self, prompt: str, memory: dict[str, Any]) -> dict[str, Any] | None:
        query = memory["query"]
        top_summary = memory["top_summary"]
        last_next_actions = memory["last_next_actions"]
        top_evidence_items = memory["top_evidence_items"]
        evidence_items = memory["evidence_items"]
        caveat_items = memory["caveat_items"]
        next_items = memory["next_items"]

        if self._prompt_is(prompt, "make that more concise", "be more concise", "shorter version") and top_summary:
            concise = top_summary.split(".")[0].strip() or top_summary
            return self._explain_response(
                query=query,
                assumption="Concise phrasing is derived from the last completed investigation turn.",
                evidence=top_evidence_items[:2],
                findings=self._summary_findings(concise),
                caveats=caveat_items[:1],
                next_actions=next_items[:1],
            )

        if self._prompt_is(prompt, "write that for a non-technical reader", "explain that for a non-technical reader", "plain english version") and top_summary:
            plain = f"In simple terms: {top_summary}"
            return self._explain_response(
                query=query,
                assumption="Plain-language wording is derived from the last completed investigation turn.",
                evidence=evidence_items[:2],
                findings=self._summary_findings(plain),
                caveats=caveat_items[:2],
                next_actions=next_items[:1],
            )

        if self._prompt_is(prompt, "turn that into a checklist", "make that a checklist", "checklist version") and (top_summary or last_next_actions):
            checklist = []
            if top_summary:
                checklist.append(f"Review finding: {top_summary}")
            checklist.extend(next_items)
            return self._explain_response(
                query=query,
                assumption="Checklist is derived from the last completed investigation turn.",
                evidence=evidence_items[:2],
                findings=self._summary_findings(*checklist[:5]),
                caveats=caveat_items[:2],
                next_actions=checklist[:5],
            )

        if self._prompt_is(prompt, "what is the safest next command to run?", "safest next command?", "safest next step?") and last_next_actions:
            safe_next = next((item for item in next_items if item), "")
            return self._explain_response(
                query=query,
                assumption="Safest next step is chosen from the last suggested follow-up commands.",
                evidence=evidence_items[:2],
                findings=self._summary_findings(f"Safest next command: {safe_next}" if safe_next else ""),
                caveats=caveat_items[:2],
                next_actions=[safe_next] if safe_next else [],
            )

        return None

    def _handle_artifact_followup(self, prompt: str, memory: dict[str, Any]) -> dict[str, Any] | None:
        query = memory["query"]
        top_summary = memory["top_summary"]
        last_evidence = memory["last_evidence"]
        last_next_actions = memory["last_next_actions"]
        evidence_items = memory["evidence_items"]
        caveat_items = memory["caveat_items"]
        next_items = memory["next_items"]

        if self._prompt_is(prompt, "turn this into an investigation note", "investigation note", "draft an investigation note") and (top_summary or last_evidence):
            note_lines = [
                f"Subject: Procurement probe for {query or 'current scope'}",
                f"Top finding: {top_summary}" if top_summary else "Top finding: unavailable",
            ]
            note_lines.extend(f"Evidence: {item}" for item in evidence_items[:3])
            note_lines.extend(f"Caveat: {item}" for item in caveat_items[:2])
            return self._explain_response(
                query=query,
                assumption="Investigation note is synthesized from the last completed investigation turn.",
                evidence=evidence_items[:3],
                findings=self._summary_findings(*note_lines),
                caveats=caveat_items[:2],
                next_actions=next_items[:3],
            )

        if self._prompt_is(prompt, "draft a short memo", "short memo", "write a short memo") and (top_summary or last_evidence):
            memo = [
                f"Memo: Review of procurement probe for {query or 'current scope'}.",
                f"Key point: {top_summary}" if top_summary else "Key point: unavailable.",
            ]
            if caveat_items:
                memo.append(f"Caveat: {caveat_items[0]}")
            return self._explain_response(
                query=query,
                assumption="Memo is synthesized from the last completed investigation turn.",
                evidence=evidence_items[:2],
                findings=self._summary_findings(*memo),
                caveats=caveat_items[:2],
                next_actions=next_items[:2],
            )

        if self._prompt_is(prompt, "format this as findings, evidence, caveats, next steps", "format as findings evidence caveats next steps") and (top_summary or last_evidence or last_next_actions):
            structured = []
            if top_summary:
                structured.append(f"Findings: {top_summary}")
            if evidence_items[:3]:
                structured.append("Evidence: " + "; ".join(evidence_items[:3]))
            if caveat_items[:2]:
                structured.append("Caveats: " + "; ".join(caveat_items[:2]))
            if next_items[:3]:
                structured.append("Next steps: " + "; ".join(next_items[:3]))
            return self._explain_response(
                query=query,
                assumption="Structured recap is synthesized from the last completed investigation turn.",
                evidence=evidence_items[:3],
                findings=self._summary_findings(*structured),
                caveats=caveat_items[:2],
                next_actions=next_items[:3],
            )

        if self._prompt_is(prompt, "turn this into json", "make this json", "export json") and (top_summary or last_evidence or last_next_actions):
            json_blob = {
                "query": query,
                "top_finding": top_summary,
                "evidence": evidence_items[:5],
                "caveats": caveat_items[:3],
                "next_steps": next_items[:5],
            }
            return self._export_followup_response(
                query=query,
                assumption="JSON export is synthesized from the last completed investigation turn.",
                evidence=evidence_items[:5],
                findings_lines=[f"JSON: {json_blob}"],
                caveats=caveat_items[:3],
                next_actions=next_items[:5],
                export_format="json",
                export_content=json_blob,
            )

        if self._prompt_is(prompt, "make this a markdown report", "markdown report", "export markdown report") and (top_summary or last_evidence):
            report_evidence = evidence_items[:3]
            report_caveats = caveat_items[:2]
            report_next = next_items[:3]
            markdown_lines = [
                f"# Procurement Probe Report: {query or 'Current Scope'}",
                f"## Top Finding\n{top_summary}" if top_summary else "## Top Finding\nUnavailable",
            ]
            if report_evidence:
                markdown_lines.append("## Evidence\n- " + "\n- ".join(report_evidence))
            if report_caveats:
                markdown_lines.append("## Caveats\n- " + "\n- ".join(report_caveats))
            if report_next:
                markdown_lines.append("## Next Steps\n- " + "\n- ".join(report_next))
            markdown_content = "\n\n".join(markdown_lines)
            return self._export_followup_response(
                query=query,
                assumption="Markdown report is synthesized from the last completed investigation turn.",
                evidence=report_evidence,
                findings_lines=markdown_lines,
                caveats=report_caveats,
                next_actions=report_next,
                export_format="markdown",
                export_content=markdown_content,
            )

        if self._prompt_is(prompt, "export a compact case summary", "compact case summary", "case summary") and (top_summary or last_evidence):
            summary = f"Case summary: {top_summary}" if top_summary else "Case summary unavailable."
            return self._export_followup_response(
                query=query,
                assumption="Compact case summary is synthesized from the last completed investigation turn.",
                evidence=evidence_items[:2],
                findings_lines=[summary],
                caveats=caveat_items[:2],
                next_actions=next_items[:2],
                export_format="case_summary",
                export_content={
                    "query": query,
                    "summary": summary,
                    "evidence": evidence_items[:2],
                    "caveats": caveat_items[:2],
                    "next_steps": next_items[:2],
                },
            )

        if self._prompt_is(prompt, "export a csv summary", "csv summary", "export csv summary") and (top_summary or last_evidence or last_next_actions):
            csv_lines = [
                "section,detail",
                f'query,"{query}"',
                f'top_finding,"{top_summary}"',
            ]
            csv_lines.extend(f'evidence,"{item}"' for item in evidence_items[:3])
            csv_lines.extend(f'caveat,"{item}"' for item in caveat_items[:2])
            csv_lines.extend(f'next_step,"{item}"' for item in next_items[:3])
            csv_content = "\n".join(csv_lines)
            return self._export_followup_response(
                query=query,
                assumption="CSV summary is synthesized from the last completed investigation turn.",
                evidence=evidence_items[:3],
                findings_lines=["CSV summary prepared for export."],
                caveats=caveat_items[:2],
                next_actions=next_items[:3],
                export_format="csv",
                export_content=csv_content,
            )

        if self._prompt_is(prompt, "make this a case timeline", "case timeline", "export case timeline") and (top_summary or last_evidence or last_next_actions):
            timeline_lines = [
                f"# Case Timeline: {query or 'Current Scope'}",
                f"1. Probe scope established: {query or 'unspecified'}.",
                f"2. Top finding identified: {top_summary}" if top_summary else "2. Top finding unavailable.",
            ]
            if evidence_items[:2]:
                timeline_lines.append("3. Key evidence noted: " + "; ".join(evidence_items[:2]))
            if caveat_items[:2]:
                timeline_lines.append("4. Caveats recorded: " + "; ".join(caveat_items[:2]))
            if next_items[:2]:
                timeline_lines.append("5. Next analyst steps: " + "; ".join(next_items[:2]))
            timeline_content = "\n".join(timeline_lines)
            return self._export_followup_response(
                query=query,
                assumption="Case timeline is synthesized from the last completed investigation turn.",
                evidence=evidence_items[:2],
                findings_lines=timeline_lines,
                caveats=caveat_items[:2],
                next_actions=next_items[:2],
                export_format="timeline",
                export_content=timeline_content,
            )

        if self._prompt_is(prompt, "turn this into a findings table", "findings table", "export findings table") and (top_summary or last_evidence or last_next_actions):
            table_lines = [
                "| Section | Details |",
                "| --- | --- |",
                f"| Scope | {query or 'unspecified'} |",
                f"| Top finding | {top_summary or 'unavailable'} |",
            ]
            if evidence_items[:2]:
                table_lines.append(f"| Evidence | {'; '.join(evidence_items[:2])} |")
            if caveat_items[:2]:
                table_lines.append(f"| Caveats | {'; '.join(caveat_items[:2])} |")
            if next_items[:2]:
                table_lines.append(f"| Next steps | {'; '.join(next_items[:2])} |")
            table_content = "\n".join(table_lines)
            return self._export_followup_response(
                query=query,
                assumption="Findings table is synthesized from the last completed investigation turn.",
                evidence=evidence_items[:2],
                findings_lines=table_lines,
                caveats=caveat_items[:2],
                next_actions=next_items[:2],
                export_format="findings_table",
                export_content=table_content,
            )

        if self._prompt_is(prompt, "generate a handoff note for another analyst", "handoff note", "analyst handoff") and (top_summary or last_evidence or last_next_actions):
            handoff_next = next_items[:3]
            handoff = [
                f"Handoff: current scope is {query or 'unspecified'}.",
                f"Priority finding: {top_summary}" if top_summary else "Priority finding unavailable.",
                "Recommended next steps: " + ("; ".join(handoff_next) if handoff_next else "none recorded"),
            ]
            return self._export_followup_response(
                query=query,
                assumption="Handoff note is synthesized from the last completed investigation turn.",
                evidence=evidence_items[:3],
                findings_lines=handoff,
                caveats=caveat_items[:2],
                next_actions=handoff_next,
                export_format="handoff",
                export_content={
                    "scope": query or "unspecified",
                    "priority_finding": top_summary,
                    "evidence": evidence_items[:3],
                    "caveats": caveat_items[:2],
                    "next_steps": handoff_next,
                },
            )

        return None

    def _export_artifact_for_prompt(self, prompt: str, last_export_artifact: dict[str, Any] | None) -> dict[str, Any] | None:
        if not isinstance(last_export_artifact, dict):
            return None
        export_format = str(last_export_artifact.get("export_format", "")).strip().lower()
        if self._prompt_is(prompt, "re-export the last artifact", "re-export last artifact", "re-export the last structured artifact"):
            return last_export_artifact
        if prompt in _REEXPORT_FORMAT_ALIASES.get(export_format, set()):
            return last_export_artifact
        return None

    def _handle_export_audit_followup(self, prompt: str, memory: dict[str, Any]) -> dict[str, Any] | None:
        query = memory["query"]
        last_export_format = memory["last_export_format"]
        last_export_path = memory["last_export_path"]
        last_export_destination = memory["last_export_destination"]
        recent_exports = memory["recent_exports"]
        last_export_artifact = memory["last_export_artifact"]

        if self._prompt_is(prompt, "show last export destination", "last export destination", "where did the last export go?") and (last_export_destination or last_export_path):
            destination = last_export_path or last_export_destination
            return self._audit_followup_response(
                query=query,
                assumption="Export destination is replayed from the persisted session artifact log.",
                findings_lines=[f"Last export destination: {destination}"],
            )

        if self._prompt_is(prompt, "what was the last export format?", "last export format", "show last export format") and last_export_format:
            return self._audit_followup_response(
                query=query,
                assumption="Export format is replayed from the persisted session artifact log.",
                findings_lines=[f"Last export format: {last_export_format}"],
            )

        if self._prompt_is(prompt, "list prior exports", "show prior exports", "what exports have i made?") and recent_exports:
            return self._audit_followup_response(
                query=query,
                assumption="Prior exports are replayed from the persisted session artifact log.",
                findings_lines=[f"Prior export: {item}" for item in recent_exports],
            )

        selected_artifact = self._export_artifact_for_prompt(prompt, last_export_artifact)
        if isinstance(selected_artifact, dict):
            export_format = str(selected_artifact.get("export_format", "")).strip()
            export_content = selected_artifact.get("export_content")
            if export_format and export_content is not None:
                destination = last_export_path or last_export_destination or "stdout"
                return self._audit_followup_response(
                    query=query,
                    assumption="Export content is replayed from the persisted session artifact log.",
                    findings_lines=[
                        f"Re-export prepared from the last {export_format} artifact.",
                        f"Previous destination: {destination}",
                    ],
                    export={"format": export_format, "content": export_content},
                )

        return None

    def _maybe_handle_explanatory_followup(
        self,
        user_input: str,
        context: dict[str, str],
    ) -> dict[str, Any] | None:
        prompt = (user_input or "").strip().lower()
        memory = self._followup_memory(context)
        for handler in (
            self._handle_explanation_followup,
            self._handle_style_followup,
            self._handle_artifact_followup,
            self._handle_export_audit_followup,
        ):
            response = handler(prompt, memory)
            if response is not None:
                return response
        return None

    def _format_context_block(self, context: dict[str, str]) -> str:
        lines = []
        for key in (
            "agency",
            "supplier",
            "query",
            "last_intent",
            "ref_id",
            "top_ref_id",
            "top_supplier",
            "ref_candidates",
            "supplier_candidates",
        ):
            value = context.get(key, "").strip()
            if value:
                lines.append(f"- {key}: {value}")
        if not lines:
            return ""
        return "[Session context]\n" + "\n".join(lines)

    def _parse_context_hint(self, text: str) -> dict[str, str]:
        hint = (text or "").strip()
        lower = hint.lower()
        if not hint:
            return {}

        if lower.startswith("focus on "):
            value = hint[9:].strip()
            if value.isupper() and len(value.split()) <= 6:
                return {"agency": value}
            return {"query": value}
        if lower.startswith("focus "):
            value = hint[6:].strip()
            if value.isupper() and len(value.split()) <= 6:
                return {"agency": value}
            return {"query": value}
        if lower.startswith("check "):
            value = hint[6:].strip().strip('"')
            if value.isupper() and len(value.split()) <= 6:
                return {"supplier": value}
        return {}

    def _update_investigation_context(
        self,
        base_context: dict[str, str],
        response: dict[str, Any],
    ) -> dict[str, str]:
        context = {k: v for k, v in base_context.items() if v}
        intent = str(response.get("intent", "")).strip()
        query = str(response.get("query", "")).strip()
        if intent:
            context["last_intent"] = intent
        if query:
            context["query"] = query
        findings = response.get("findings", []) or []
        evidence = response.get("evidence", []) or []
        caveats = response.get("caveats", []) or []
        should_promote_findings = intent != "explain" or bool(response.get("tool_trace"))
        if findings and should_promote_findings:
            top = findings[0]
            top_summary = top.get("summary", "") if isinstance(top, dict) else str(top)
            if top_summary:
                context["top_finding_summary"] = str(top_summary)
            if len(findings) > 1:
                second = findings[1]
                second_summary = second.get("summary", "") if isinstance(second, dict) else str(second)
                if second_summary:
                    context["second_finding_summary"] = str(second_summary)
            top_evidence = top.get("evidence", {}) if isinstance(top, dict) else {}
            if isinstance(top_evidence, dict) and top_evidence:
                context["top_finding_evidence"] = " || ".join(f"{k}={v}" for k, v in top_evidence.items())
        if evidence:
            context["last_evidence"] = " || ".join(str(item) for item in evidence[:8])
        if caveats:
            context["last_caveats"] = " || ".join(str(item) for item in caveats[:8])
        next_actions = response.get("next_actions", []) or []
        if next_actions:
            context["last_next_actions"] = " || ".join(str(item) for item in next_actions[:8])

        for step in response.get("tool_trace", []) or []:
            args = step.get("args", {}) or {}
            tool = step.get("tool", "")
            payload = step.get("payload")
            if tool == "probe":
                if args.get("agency"):
                    context["agency"] = str(args["agency"])
                if args.get("query"):
                    context["query"] = str(args["query"])
                if isinstance(payload, dict):
                    findings = payload.get("findings", []) or []
                    ref_candidates: list[str] = []
                    supplier_candidates: list[str] = []
                    for finding in findings:
                        for ref in finding.get("refs", []) or []:
                            if ref and ref not in ref_candidates:
                                ref_candidates.append(str(ref))
                        evidence = finding.get("evidence", {}) or {}
                        supplier_name = evidence.get("supplier")
                        if supplier_name and supplier_name not in supplier_candidates:
                            supplier_candidates.append(str(supplier_name))
                    if ref_candidates:
                        context["top_ref_id"] = ref_candidates[0]
                        context["ref_candidates"] = ",".join(ref_candidates[:5])
                    if supplier_candidates:
                        context["top_supplier"] = supplier_candidates[0]
                        context["supplier_candidates"] = "|".join(supplier_candidates[:5])
            elif tool == "awards":
                if args.get("agency"):
                    context["agency"] = str(args["agency"])
                if args.get("supplier"):
                    context["supplier"] = str(args["supplier"])
                if isinstance(payload, list) and payload:
                    ref_candidates = [str(item.get("ref_no")) for item in payload if isinstance(item, dict) and item.get("ref_no")]
                    supplier_candidates = [str(item.get("supplier")) for item in payload if isinstance(item, dict) and item.get("supplier")]
                    if ref_candidates:
                        deduped_refs = list(dict.fromkeys(ref_candidates))
                        context["top_ref_id"] = deduped_refs[0]
                        context["ref_candidates"] = ",".join(deduped_refs[:5])
                    if supplier_candidates:
                        deduped_suppliers = list(dict.fromkeys(supplier_candidates))
                        context["top_supplier"] = deduped_suppliers[0]
                        context["supplier_candidates"] = "|".join(deduped_suppliers[:5])
            elif tool == "supplier":
                if args.get("name"):
                    context["supplier"] = str(args["name"])
            elif tool == "network":
                if args.get("supplier_name"):
                    context["supplier"] = str(args["supplier_name"])
            elif tool == "agency":
                if args.get("name"):
                    context["agency"] = str(args["name"])
            elif tool == "split":
                if args.get("agency"):
                    context["agency"] = str(args["agency"])
            elif tool == "overprice":
                if args.get("category"):
                    context["query"] = str(args["category"])
            elif tool == "detail":
                if args.get("ref_id"):
                    context["ref_id"] = str(args["ref_id"])
                    context["top_ref_id"] = str(args["ref_id"])
                    context["ref_candidates"] = str(args["ref_id"])

        return context


class AgentSessionLogger(JsonlTurnLogger):
    def __init__(self, path: Path | None = None):
        super().__init__(path or (Path.home() / ".probid" / "agent-sessions.jsonl"))
