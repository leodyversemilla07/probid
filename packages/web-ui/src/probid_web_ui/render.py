"""HTML rendering helpers for probid web UI."""

from __future__ import annotations

from probid_web_ui.types import (
    AgencyProfile,
    AwardRecord,
    Finding,
    NoticeData,
    ProbeResult,
    SupplierProfile,
)


def escape_html(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def format_currency_html(amount: float | None, currency: str = "PHP") -> str:
    """Format currency as HTML."""
    if amount is None or amount <= 0:
        return '<span class="currency-missing">—</span>'
    if amount >= 1_000_000_000:
        return f'<span class="currency">{currency} {amount / 1_000_000_000:,.2f}B</span>'
    if amount >= 1_000_000:
        return f'<span class="currency">{currency} {amount / 1_000_000:,.2f}M</span>'
    if amount >= 1_000:
        return f'<span class="currency">{currency} {amount / 1_000:,.2f}K</span>'
    return f'<span class="currency">{currency} {amount:,.2f}</span>'


def render_notice_row(notice: NoticeData) -> str:
    """Render a notice as an HTML table row."""
    return f"""<tr>
    <td>{escape_html(notice.ref_id)}</td>
    <td>{escape_html(notice.title or "")}</td>
    <td>{escape_html(notice.published_date or "—")}</td>
    <td>{format_currency_html(notice.budget)}</td>
</tr>"""


def render_notices_table(notices: list[NoticeData], query: str = "") -> str:
    """Render a table of notices."""
    title = "Procurement Notices"
    if query:
        title += f' - "{escape_html(query)}"'

    rows = "\n".join(render_notice_row(n) for n in notices)

    return f"""<table class="notices-table">
    <thead>
        <tr>
            <th>Ref No</th>
            <th>Title</th>
            <th>Published</th>
            <th>Budget</th>
        </tr>
    </thead>
    <tbody>
        {rows if rows else '<tr><td colspan="4">No results found.</td></tr>'}
    </tbody>
</table>"""


def render_finding(finding: Finding) -> str:
    """Render a finding with appropriate risk styling."""
    confidence_class = f"confidence-{finding.confidence}"
    return f"""<div class="finding {confidence_class}">
        <span class="finding-code">{escape_html(finding.code)}</span>
        <span class="finding-desc">{escape_html(finding.description)}</span>
    </div>"""


def render_probe_result(result: ProbeResult) -> str:
    """Render a probe result."""
    findings_html = "\n".join(render_finding(f) for f in result.findings)

    quality_class = f"quality-{result.data_quality}"
    summary_stats = result.summary.get("records_scanned", 0)

    return f"""<div class="probe-result {quality_class}">
    <div class="summary">
        <h3>Summary</h3>
        <p>Records scanned: {summary_stats}</p>
        <p>Data quality: {result.data_quality}</p>
    </div>
    <div class="findings">
        <h3>Findings ({len(result.findings)})</h3>
        {findings_html if findings_html else "<p>No findings.</p>"}
    </div>
</div>"""


def render_supplier_profile(profile: SupplierProfile) -> str:
    """Render a supplier profile."""
    agencies = ", ".join(escape_html(a) for a in profile.agencies) if profile.agencies else "—"

    return f"""<div class="supplier-profile">
    <h2>{escape_html(profile.name)}</h2>
    <dl>
        <dt>Total Contracts</dt><dd>{profile.total_contracts}</dd>
        <dt>Total Wins</dt><dd>{profile.total_wins}</dd>
        <dt>Total Awarded</dt><dd>{format_currency_html(profile.total_awarded_amount)}</dd>
        <dt>Agencies</dt><dd>{agencies}</dd>
    </dl>
</div>"""


def render_agency_profile(profile: AgencyProfile) -> str:
    """Render an agency profile."""
    return f"""<div class="agency-profile">
    <h2>{escape_html(profile.name)}</h2>
    <dl>
        <dt>Total Contracts</dt><dd>{profile.total_contracts}</dd>
        <dt>Total Budget</dt><dd>{format_currency_html(profile.total_budget)}</dd>
        <dt>Categories</dt><dd>{", ".join(escape_html(c) for c in profile.categories) if profile.categories else "—"}</dd>
    </dl>
</div>"""


def render_awards_table(awards: list[AwardRecord]) -> str:
    """Render a table of award records."""
    rows = "\n".join(
        f"""<tr>
    <td>{escape_html(a.ref_id)}</td>
    <td>{escape_html(a.agency)}</td>
    <td>{escape_html(a.supplier)}</td>
    <td>{format_currency_html(a.awarded_amount)}</td>
</tr>"""
        for a in awards
    )

    return f"""<table class="awards-table">
    <thead>
        <tr>
            <th>Ref No</th>
            <th>Agency</th>
            <th>Supplier</th>
            <th>Amount</th>
        </tr>
    </thead>
    <tbody>
        {rows if rows else '<tr><td colspan="4">No awards found.</td></tr>'}
    </tbody>
</table>"""
