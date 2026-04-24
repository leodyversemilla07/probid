"""Intent planner for probid agent."""

from __future__ import annotations

import re
from typing import Any

from probid_agent.types import ExecutionPlan, PlanStep

_REF_RE = re.compile(r"\b\d{5,}\b")
_AGENCY_RE = re.compile(r"\b(?:in|for|at|from)\s+([A-Z][A-Z0-9&()\- ]{2,}|[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\b")
_SUPPLIER_QUOTED_RE = re.compile(r'"([^"]+)"')
_SESSION_CONTEXT_RE = re.compile(r"\[Session context\]\n(?P<body>(?:- .+\n?)*)", re.IGNORECASE)
_STOPWORDS = {
    "probe",
    "search",
    "check",
    "analyze",
    "analyse",
    "find",
    "look into",
    "inspect",
    "awards",
    "award",
    "risks",
    "risk",
    "suspicious",
    "patterns",
    "pattern",
    "possible",
    "split",
    "splitting",
    "contracts",
    "contract",
    "supplier",
    "agency",
    "profile",
    "repeat",
    "concentration",
    "network",
    "overprice",
    "pricing",
    "procurement",
    "tell me",
    "show me",
    "look at",
    "for",
    "in",
    "from",
    "with",
    "and",
    "then",
}


def _strip_session_context(text: str) -> tuple[str, dict[str, str]]:
    match = _SESSION_CONTEXT_RE.search(text or "")
    if not match:
        return text, {}

    context: dict[str, str] = {}
    for raw_line in match.group("body").splitlines():
        line = raw_line.strip()
        if not line.startswith("- ") or ":" not in line:
            continue
        key, value = line[2:].split(":", 1)
        context[key.strip().lower()] = value.strip()

    cleaned = ((text or "")[: match.start()] + (text or "")[match.end() :]).strip()
    return cleaned, context


def _extract_query(text: str) -> str:
    cleaned = " ".join(text.strip().split())
    for prefix in (
        "probe ",
        "search ",
        "check ",
        "analyze ",
        "analyse ",
        "find ",
        "look into ",
        "inspect ",
    ):
        if cleaned.lower().startswith(prefix):
            cleaned = cleaned[len(prefix) :].strip() or cleaned
            break

    cleaned = re.sub(r"\b(?:tell|show) me\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:if|whether) anything looks? risky\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bpossible\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.-")
    return cleaned or text.strip()


def _extract_agency(text: str) -> str:
    quoted = _SUPPLIER_QUOTED_RE.findall(text)
    for value in quoted:
        if value.isupper() and len(value.split()) <= 6:
            return value.strip()

    match = _AGENCY_RE.search(text)
    if not match:
        return ""
    value = match.group(1).strip(" ,.-")
    if len(value) < 3:
        return ""
    return value


def _extract_supplier_name(text: str) -> str:
    quoted = _SUPPLIER_QUOTED_RE.findall(text)
    if quoted:
        return quoted[0].strip()

    match = re.search(r"\bsupplier\s+([A-Z][A-Za-z0-9&.,()\- ]+)", text)
    if match:
        return match.group(1).strip(" ,.-")
    return ""


def _extract_subject_query(text: str, agency: str = "", supplier: str = "") -> str:
    cleaned = _extract_query(text)

    for phrase in (
        "repeat awardees",
        "repeat awards",
        "supplier concentration",
        "contract splitting",
    ):
        cleaned = re.sub(re.escape(phrase), "", cleaned, flags=re.IGNORECASE)

    if agency:
        cleaned = re.sub(
            rf"\b(?:in|for|at|from)\s+{re.escape(agency)}\b",
            "",
            cleaned,
            flags=re.IGNORECASE,
        )
    if supplier:
        cleaned = cleaned.replace(f'"{supplier}"', "")
        cleaned = re.sub(rf"\bsupplier\s+{re.escape(supplier)}\b", "", cleaned, flags=re.IGNORECASE)

    parts = [p for p in re.split(r"\s+", cleaned) if p and p.lower() not in _STOPWORDS]
    return " ".join(parts).strip(" ,.-")


def _to_cli_equivalent(tool: str, args: dict[str, Any]) -> str:
    if tool == "detail":
        return f"probid detail {args.get('ref_id', '')}".strip()
    if tool == "awards":
        parts = ["probid awards"]
        if args.get("agency"):
            parts.append(f'--agency "{args["agency"]}"')
        if args.get("supplier"):
            parts.append(f'--supplier "{args["supplier"]}"')
        if args.get("limit"):
            parts.append(f"--limit {args['limit']}")
        return " ".join(parts)
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
        cli = f'probid search "{q}"'
        if args.get("agency"):
            cli += f' --agency "{args["agency"]}"'
        return cli
    if tool == "network":
        return f'probid network "{args.get("supplier_name", "")}"'
    if tool == "overprice":
        return f'probid overprice "{args.get("category", "")}" --threshold {args.get("threshold", 200)}'

    q = args.get("query", "")
    min_conf = args.get("min_confidence", "low")
    max_findings = args.get("max_findings", 5)
    pages = args.get("pages", 1)
    cli = f'probid probe "{q}" --pages {pages} --min-confidence {min_conf} --max-findings {max_findings}'
    if args.get("agency"):
        cli += f' --agency "{args["agency"]}"'
    return cli


def _step(tool: str, args: dict[str, Any]) -> PlanStep:
    return {
        "tool": tool,
        "args": args,
        "cli_equivalent": _to_cli_equivalent(tool, args),
    }


_SUPPORTED_TOOLS = {
    "probe",
    "search",
    "detail",
    "awards",
    "supplier",
    "agency",
    "repeat",
    "split",
    "network",
    "overprice",
}


def supported_tools() -> set[str]:
    return set(_SUPPORTED_TOOLS)


def normalize_plan(plan: dict[str, Any]) -> dict[str, Any]:
    normalized = {
        "intent": plan.get("intent", "probe"),
        "query": plan.get("query", ""),
        "steps": [],
    }
    for step in plan.get("steps", []):
        tool = step.get("tool")
        if tool not in _SUPPORTED_TOOLS:
            raise ValueError(f"Unsupported tool '{tool}' in AI plan")
        args = step.get("args", {}) or {}
        normalized["steps"].append(
            {
                "tool": tool,
                "args": args,
                "cli_equivalent": step.get("cli_equivalent") or _to_cli_equivalent(tool, args),
            }
        )
    return normalized


def _candidate_list(raw: str, sep: str = ",") -> list[str]:
    return [item.strip() for item in (raw or "").split(sep) if item.strip()]


def plan_for_input(user_input: str) -> ExecutionPlan:
    raw_text = (user_input or "").strip()
    text, session_context = _strip_session_context(raw_text)
    lower = text.lower()
    query = _extract_query(text)
    agency = _extract_agency(text) or session_context.get("agency", "")
    supplier = _extract_supplier_name(text) or session_context.get("supplier", "")
    context_query = session_context.get("query", "")
    ref_candidates = _candidate_list(session_context.get("ref_candidates", ""), sep=",")
    supplier_candidates = _candidate_list(session_context.get("supplier_candidates", ""), sep="|")
    top_ref_id = (
        session_context.get("top_ref_id", "")
        or session_context.get("ref_id", "")
        or (ref_candidates[0] if ref_candidates else "")
    )
    top_supplier = (
        session_context.get("top_supplier", "") or supplier or (supplier_candidates[0] if supplier_candidates else "")
    )
    second_supplier = supplier_candidates[1] if len(supplier_candidates) > 1 else top_supplier
    most_recent_award_ref = ref_candidates[0] if ref_candidates else top_ref_id
    subject_query = _extract_subject_query(text, agency=agency, supplier=supplier) or query or context_query

    if lower in {"why", "why?", "show why", "show me why"} and (context_query or subject_query):
        probe_query = context_query or subject_query
        return {
            "intent": "probe",
            "query": probe_query,
            "steps": [
                _step(
                    "probe",
                    {
                        "query": probe_query,
                        "pages": 1,
                        "min_confidence": "low",
                        "max_findings": 5,
                        "agency": agency,
                    },
                )
            ],
        }

    if any(
        phrase in lower
        for phrase in [
            "high confidence",
            "only high confidence",
            "show only high confidence",
        ]
    ):
        probe_query = context_query or subject_query
        return {
            "intent": "probe",
            "query": probe_query,
            "steps": [
                _step(
                    "probe",
                    {
                        "query": probe_query,
                        "pages": 1,
                        "min_confidence": "high",
                        "max_findings": 5,
                        "agency": agency,
                    },
                )
            ],
        }

    if any(
        phrase in lower
        for phrase in [
            "detail the first ref",
            "detail first ref",
            "show the first ref",
            "open the first ref",
            "drill into the top finding",
        ]
    ):
        if top_ref_id:
            return {
                "intent": "detail",
                "query": top_ref_id,
                "steps": [_step("detail", {"ref_id": top_ref_id})],
            }

    if any(phrase in lower for phrase in ["open the most recent award", "show the most recent award"]):
        if most_recent_award_ref:
            return {
                "intent": "detail",
                "query": most_recent_award_ref,
                "steps": [_step("detail", {"ref_id": most_recent_award_ref})],
            }

    if any(
        phrase in lower
        for phrase in [
            "supplier behind that",
            "check the supplier behind that",
            "show the supplier behind that",
        ]
    ):
        if top_supplier:
            return {
                "intent": "supplier",
                "query": top_supplier,
                "steps": [_step("supplier", {"name": top_supplier})],
            }

    if any(
        phrase in lower
        for phrase in [
            "show the second supplier",
            "check the second supplier",
            "open the second supplier",
        ]
    ):
        if second_supplier:
            return {
                "intent": "supplier",
                "query": second_supplier,
                "steps": [_step("supplier", {"name": second_supplier})],
            }

    if any(k in lower for k in ["detail", "reference", "ref ", "ref#", "ref no"]):
        match = _REF_RE.search(text)
        if match:
            return {
                "intent": "detail",
                "query": match.group(0),
                "steps": [_step("detail", {"ref_id": match.group(0)})],
            }

    if any(k in lower for k in ["split", "splitting"]):
        agency_name = agency or subject_query or query or context_query
        return {
            "intent": "split",
            "query": agency_name,
            "steps": [_step("split", {"agency": agency_name, "gap_days": 30})],
        }

    if "overprice" in lower or (
        "pricing" in lower and not any(k in lower for k in ["probe", "risk", "suspicious", "check"])
    ):
        category = subject_query or query or context_query
        return {
            "intent": "overprice",
            "query": category,
            "steps": [_step("overprice", {"category": category, "threshold": 200})],
        }

    if "supplier" in lower and supplier and any(k in lower for k in ["network", "competitor", "concentration"]):
        return {
            "intent": "supplier",
            "query": supplier,
            "steps": [
                _step("supplier", {"name": supplier}),
                _step("network", {"supplier_name": supplier}),
                _step("repeat", {"min_count": 3}),
            ],
        }

    if "supplier" in lower and supplier:
        return {
            "intent": "supplier",
            "query": supplier,
            "steps": [_step("supplier", {"name": supplier})],
        }

    if "agency" in lower and agency:
        return {
            "intent": "agency",
            "query": agency,
            "steps": [_step("agency", {"name": agency})],
        }

    if any(k in lower for k in ["repeat", "concentration"]):
        return {
            "intent": "repeat",
            "query": subject_query or query or context_query,
            "steps": [_step("repeat", {"min_count": 3})],
        }

    if any(k in lower for k in ["awards", "award"]) and any(
        k in lower for k in ["probe", "risk", "suspicious", "analy", "check"]
    ):
        probe_query = subject_query or query or context_query
        return {
            "intent": "probe",
            "query": probe_query,
            "steps": [
                _step("awards", {"agency": agency, "supplier": supplier, "limit": 50}),
                _step(
                    "probe",
                    {
                        "query": probe_query,
                        "pages": 1,
                        "min_confidence": "low",
                        "max_findings": 5,
                        "agency": agency,
                    },
                ),
            ],
        }

    if "awards" in lower or "award" in lower:
        return {
            "intent": "awards",
            "query": subject_query or query or context_query,
            "steps": [_step("awards", {"agency": agency, "supplier": supplier, "limit": 50})],
        }

    if any(
        k in lower
        for k in [
            "probe",
            "risk",
            "suspicious",
            "analy",
            "check",
            "look into",
            "inspect",
        ]
    ):
        probe_query = subject_query or query or context_query
        steps = []
        if agency or supplier:
            steps.append(_step("awards", {"agency": agency, "supplier": supplier, "limit": 50}))
        steps.append(
            _step(
                "probe",
                {
                    "query": probe_query,
                    "pages": 1,
                    "min_confidence": "low",
                    "max_findings": 5,
                    "agency": agency,
                },
            )
        )
        return {
            "intent": "probe",
            "query": probe_query,
            "steps": steps,
        }

    return {
        "intent": "probe",
        "query": subject_query or query or context_query,
        "steps": [
            _step(
                "probe",
                {
                    "query": subject_query or query or context_query,
                    "pages": 1,
                    "min_confidence": "low",
                    "max_findings": 5,
                    "agency": agency,
                },
            )
        ],
    }
