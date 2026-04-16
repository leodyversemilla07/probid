# @probid/web-ui

Web UI package for probid.

Status: **extracted** — provides HTML rendering primitives and typed data models.

## Features

- **Typed data models** — `NoticeData`, `SearchResult`, `Finding`, `ProbeResult`, `AgencyProfile`, `SupplierProfile`, `AwardRecord`
- **HTML rendering helpers** — `render_notices_table()`, `render_probe_result()`, `render_supplier_profile()`, `render_agency_profile()`, `render_awards_table()`
- **Utilities** — `escape_html()`, `format_currency_html()`

## Usage

```python
from probid_web_ui.types import NoticeData, ProbeResult, Finding
from probid_web_ui import render_notices_table

# Render notice table
notices = [
    NoticeData(ref_id="12905086", title="Laptop Procurement", budget=1500000),
    NoticeData(ref_id="12905087", title="Server Upgrade", budget=5000000),
]
html = render_notices_table(notices, query="procurement")
print(html)
```

## Testing

```bash
python3 -m unittest packages/web-ui/tests -v
```
