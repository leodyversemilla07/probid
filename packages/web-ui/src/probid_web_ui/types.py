"""Web UI types for probid."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class NoticeData:
    """Data for a procurement notice."""

    ref_id: str
    title: str
    published_date: str | None = None
    closing_date: str | None = None
    category: str | None = None
    description: str | None = None
    budget: float | None = None
    agency: str | None = None
    winning_bidder: str | None = None
    awarded_amount: float | None = None


@dataclass
class SearchResult:
    """Search result for procurement data."""

    notices: list[NoticeData] = field(default_factory=list)
    total_count: int = 0
    query: str = ""


@dataclass
class Finding:
    """A risk/triage finding."""

    code: str  # e.g., "R1", "R2"
    description: str
    confidence: str = "medium"  # low, medium, high


@dataclass
class ProbeResult:
    """Result of a probe operation."""

    summary: dict[str, Any] = field(default_factory=dict)
    findings: list[Finding] = field(default_factory=list)
    data_quality: str = "adequate"  # adequate, limited, constrained


@dataclass
class AgencyProfile:
    """Agency profile data."""

    name: str
    total_contracts: int = 0
    total_budget: float = 0.0
    top_suppliers: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)


@dataclass
class SupplierProfile:
    """Supplier profile data."""

    name: str
    total_contracts: int = 0
    total_wins: int = 0
    total_awarded_amount: float = 0.0
    agencies: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)


@dataclass
class AwardRecord:
    """Contract award record."""

    ref_id: str
    agency: str
    supplier: str
    awarded_amount: float
    award_date: str | None = None
    category: str | None = None
