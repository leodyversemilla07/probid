"""Web UI package for probid."""

from probid_web_ui.types import (
    AgencyProfile,
    AwardRecord,
    Finding,
    NoticeData,
    ProbeResult,
    SearchResult,
    SupplierProfile,
)

__all__ = [
    # Types
    "NoticeData",
    "SearchResult",
    "Finding",
    "ProbeResult",
    "AgencyProfile",
    "SupplierProfile",
    "AwardRecord",
]


def create_app():
    """Create a new probid web application instance."""
    from probid_web_ui._app import ProbidWebApp
    return ProbidWebApp()


def render_notices_table(*args, **kwargs):
    from probid_web_ui.render import render_notices_table as _fn
    return _fn(*args, **kwargs)


def render_probe_result(*args, **kwargs):
    from probid_web_ui.render import render_probe_result as _fn
    return _fn(*args, **kwargs)


def escape_html(*args, **kwargs):
    from probid_web_ui.render import escape_html as _fn
    return _fn(*args, **kwargs)


def format_currency_html(*args, **kwargs):
    from probid_web_ui.render import format_currency_html as _fn
    return _fn(*args, **kwargs)
