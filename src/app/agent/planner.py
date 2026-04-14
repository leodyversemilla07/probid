"""Intent planner for probid agent."""

from __future__ import annotations

import re
from typing import Any


_REF_RE = re.compile(r"\b\d{5,}\b")


def _extract_query(text: str) -> str:
    cleaned = text.strip()
    for prefix in (
        "probe ",
        "search ",
        "check ",
        "analyze ",
        "analyse ",
        "find ",
    ):
        if cleaned.lower().startswith(prefix):
            return cleaned[len(prefix) :].strip() or cleaned
    return cleaned


def _to_cli_equivalent(tool: str, args: dict[str, Any]) -> str:
    if tool == "detail":
        return f"probid detail {args.get('ref_id', '')}".strip()
    if tool == "awards":
        return "probid awards"
    if tool == "supplier":
        name = args.get("name", "")
        return f'probid supplier "{name}"'
    if tool == "agency":
        name = args.get("name", "")
        return f'probid agency "{name}"'
    if tool == "repeat":
        return f"probid repeat --min-count {args.get('min_count', 3)}"
    if tool == "split":
        agency = args.get("agency", "")
        return f'probid split "{agency}" --gap-days {args.get("gap_days", 30)}'
    if tool == "search":
        q = args.get("query", "")
        return f'probid search "{q}"'

    q = args.get("query", "")
    min_conf = args.get("min_confidence", "low")
    max_findings = args.get("max_findings", 5)
    pages = args.get("pages", 1)
    return (
        f'probid probe "{q}" --pages {pages} '
        f"--min-confidence {min_conf} --max-findings {max_findings}"
    )


def _step(tool: str, args: dict[str, Any]) -> dict[str, Any]:
    return {
        "tool": tool,
        "args": args,
        "cli_equivalent": _to_cli_equivalent(tool, args),
    }


def plan_for_input(user_input: str) -> dict[str, Any]:
    text = (user_input or "").strip()
    lower = text.lower()
    query = _extract_query(text)

    if any(k in lower for k in ["detail", "reference", "ref ", "ref#", "ref no"]):
        match = _REF_RE.search(text)
        if match:
            return {
                "intent": "detail",
                "query": match.group(0),
                "steps": [_step("detail", {"ref_id": match.group(0)})],
            }

    if "awards" in lower or "award" in lower:
        return {
            "intent": "awards",
            "query": query,
            "steps": [_step("awards", {"limit": 50})],
        }

    if "supplier" in lower:
        return {
            "intent": "supplier",
            "query": query,
            "steps": [_step("supplier", {"name": query})],
        }

    if "agency" in lower:
        return {
            "intent": "agency",
            "query": query,
            "steps": [_step("agency", {"name": query})],
        }

    if any(k in lower for k in ["repeat", "concentration"]):
        return {
            "intent": "repeat",
            "query": query,
            "steps": [_step("repeat", {"min_count": 3})],
        }

    if any(k in lower for k in ["split", "splitting"]):
        return {
            "intent": "split",
            "query": query,
            "steps": [_step("split", {"agency": query, "gap_days": 30})],
        }

    return {
        "intent": "probe",
        "query": query,
        "steps": [
            _step(
                "probe",
                {
                    "query": query,
                    "pages": 1,
                    "min_confidence": "low",
                    "max_findings": 5,
                },
            )
        ],
    }
