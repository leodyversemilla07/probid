"""Data models for procurement notices, awards, and suppliers.

These are reference models — the scraper and cache currently use plain dicts.
Import these if you want typed access to the data.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict


class NoticeType:
    INVITATION_TO_BID = "Invitation to Bid"
    REQUEST_FOR_QUOTATION = "Request for Quotation"
    REQUEST_FOR_PROPOSAL = "Request for Proposal"
    POST_QUALIFICATION = "Post Qualification"
    AWARD_NOTICE = "Award Notice"
    CONTRACT_AWARD = "Contract Award"
    OTHER = "Other"


@dataclass
class ProcurementNotice:
    """A single procurement notice from PhilGEPS."""
    ref_no: str
    title: str
    agency: str
    notice_type: str = ""
    category: str = ""
    area_of_delivery: str = ""
    posted_date: str = ""
    closing_date: str = ""
    approved_budget: float = 0.0
    description: str = ""
    url: str = ""
    documents: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> ProcurementNotice:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Award:
    """A contract award record."""
    ref_no: str
    project_title: str
    agency: str
    supplier: str
    award_amount: float = 0.0
    award_date: str = ""
    approved_budget: float = 0.0
    bid_type: str = ""
    url: str = ""

    @property
    def budget_utilization(self) -> float:
        """Percentage of budget used (100 = exact, <100 = savings)."""
        if self.approved_budget <= 0:
            return 0.0
        return (self.award_amount / self.approved_budget) * 100

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Award:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class Supplier:
    """A supplier/contractor profile."""
    name: str
    total_awards: int = 0
    total_value: float = 0.0
    agencies_served: list[str] = field(default_factory=list)
    first_seen: str = ""
    last_seen: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Supplier:
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


@dataclass
class AgencyProfile:
    """Aggregate stats for a procuring entity."""
    name: str
    total_notices: int = 0
    total_awards: int = 0
    total_spending: float = 0.0
    top_suppliers: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)
