"""First-class tool definitions for the probid agent harness."""

from __future__ import annotations

import json
from typing import Any

from probid_agent.agent import ToolRegistry
from probid_agent.types import ToolSpec
from probid_probing_agent.core import analysis
from probid_probing_agent.core.data import cache


class AgentToolAdapter:
    """Compatibility layer for the existing harness tool surface."""

    def __init__(self, conn):
        self.conn = conn

    def probe(
        self,
        query: str,
        pages: int = 1,
        min_confidence: str = "low",
        max_findings: int = 5,
        agency: str = "",
    ) -> dict[str, Any]:
        return analysis.analyze_probe_findings(
            self.conn,
            query=query,
            agency=agency,
            pages_scanned=max(1, pages),
            min_confidence=min_confidence.lower(),
            max_findings=max(1, max_findings),
        )

    def search(self, query: str, agency: str = "", limit: int = 20) -> list[dict[str, Any]]:
        return cache.search_notices(self.conn, query=query, agency=agency, limit=limit)

    def detail(self, ref_id: str) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM notices WHERE ref_no = ?", (ref_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        try:
            data["documents"] = json.loads(data.get("documents", "[]"))
        except (json.JSONDecodeError, TypeError):
            data["documents"] = []
        return data

    def awards(self, agency: str = "", supplier: str = "", limit: int = 20) -> list[dict[str, Any]]:
        return cache.search_awards(self.conn, agency=agency, supplier=supplier, limit=limit)

    def supplier(self, name: str) -> dict[str, Any]:
        return {
            "stats": cache.get_supplier_stats(self.conn, name),
            "awards": cache.search_awards(self.conn, supplier=name, limit=20),
        }

    def agency(self, name: str) -> dict[str, Any]:
        return {
            "stats": cache.get_agency_stats(self.conn, name),
            "awards": cache.search_awards(self.conn, agency=name, limit=20),
        }

    def repeat(self, min_count: int = 3) -> list[dict[str, Any]]:
        return analysis.find_repeat_awardees(self.conn, min_count=min_count)

    def split(self, agency: str, gap_days: int = 30) -> list[dict[str, Any]]:
        return analysis.detect_split_contracts(self.conn, agency=agency, max_gap_days=gap_days)


def build_tool_registry(conn) -> ToolRegistry:
    adapter = AgentToolAdapter(conn)
    return ToolRegistry(
        [
            ToolSpec(
                name="agency",
                description="Inspect a procuring entity profile from the local cache.",
                parameters=("name",),
                handler=adapter.agency,
            ),
            ToolSpec(
                name="awards",
                description="List recent contract awards from the local cache.",
                parameters=("agency", "supplier", "limit"),
                handler=adapter.awards,
            ),
            ToolSpec(
                name="detail",
                description="Fetch a cached notice detail by reference number.",
                parameters=("ref_id",),
                handler=adapter.detail,
            ),
            ToolSpec(
                name="probe",
                description="Run a summary-first procurement probe with explainable findings.",
                parameters=("query", "pages", "min_confidence", "max_findings", "agency"),
                handler=adapter.probe,
            ),
            ToolSpec(
                name="repeat",
                description="Find repeat awardees above a minimum count threshold.",
                parameters=("min_count",),
                handler=adapter.repeat,
            ),
            ToolSpec(
                name="search",
                description="Search cached procurement notices by query and agency.",
                parameters=("query", "agency", "limit"),
                handler=adapter.search,
            ),
            ToolSpec(
                name="split",
                description="Detect potential split-contract clusters for an agency.",
                parameters=("agency", "gap_days"),
                handler=adapter.split,
            ),
            ToolSpec(
                name="supplier",
                description="Inspect a supplier profile and recent awards from the local cache.",
                parameters=("name",),
                handler=adapter.supplier,
            ),
        ]
    )
