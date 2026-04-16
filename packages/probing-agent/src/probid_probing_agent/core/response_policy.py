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
        _ = context
        _ = envelope
        # Reserved for future procurement-specific metadata/caveat enrichment.
        return
