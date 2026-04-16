"""PhilGEPS scraper using Playwright for browser automation.

PhilGEPS is an ASP.NET WebForms app using __doPostBack for navigation.
Playwright handles the JS execution that simple HTTP clients can't.
"""

from __future__ import annotations

import atexit
import re
import logging
import time
from functools import wraps
from typing import Callable
from urllib.parse import urljoin

logger = logging.getLogger(__name__)

BASE_URL = "https://notices.philgeps.gov.ph/GEPSNONPILOT"
SEARCH_URL = f"{BASE_URL}/Tender/SplashOpenOpportunitiesUI.aspx?ClickFrom=OpenOpp&menuIndex=3"
AWARDS_URL = f"{BASE_URL}/Tender/RecentAwardNoticeUI.aspx?menuIndex=3"
DETAIL_URL = f"{BASE_URL}/Tender/SplashBidNoticeAbstractUI.aspx"

# Rate limiting: minimum seconds between requests
_MIN_REQUEST_INTERVAL = 2.0
_last_request_time = 0.0

# Shared browser instance (lazy init)
_browser = None
_context = None
_pw = None


def _rate_limit():
    """Enforce minimum interval between requests."""
    global _last_request_time
    now = time.monotonic()
    elapsed = now - _last_request_time
    if elapsed < _MIN_REQUEST_INTERVAL:
        time.sleep(_MIN_REQUEST_INTERVAL - elapsed)
    _last_request_time = time.monotonic()


def _retry(max_attempts: int = 2):
    """Decorator: retry a function on Playwright/browser/network errors.

    Only retries on browser lifecycle errors (closed context, crashed page,
    timeout, connection reset). Does NOT retry programming errors
    (TypeError, ValueError, KeyError, AttributeError) or permanent OS errors
    (disk full, permission denied).
    """
    # Transient network/browser error patterns — must be specific to avoid false matches
    _TRANSIENT_PATTERNS = (
        "closed", "target closed", "page crashed", "browser closed",
        "timeout", "timed out",
        "connection reset", "connection refused", "connection closed",
        "net::err_", "disconnected",
    )

    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            last_err = None
            for attempt in range(max_attempts):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    msg = str(e).lower()
                    is_transient = any(p in msg for p in _TRANSIENT_PATTERNS)
                    if not is_transient:
                        raise  # Programming error or permanent OS error — don't retry
                    last_err = e
                    _handle_retry(e, attempt, max_attempts)
            raise last_err
        return wrapper
    return decorator


def _handle_retry(e: Exception, attempt: int, max_attempts: int):
    """Handle retry logic: reset browser if dead, sleep, log."""
    msg = str(e).lower()
    # Only reset browser for browser-lifecycle errors, not timeouts
    if any(kw in msg for kw in ("closed", "crashed", "disconnected")):
        _reset_browser()
    if attempt < max_attempts - 1:
        logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying...")
        time.sleep(1)


def _reset_browser():
    """Reset browser state after a crash."""
    global _browser, _context, _pw
    logger.info("Resetting browser after crash...")
    try:
        if _context:
            _context.close()
    except Exception:
        pass
    try:
        if _browser:
            _browser.close()
    except Exception:
        pass
    try:
        if _pw:
            _pw.stop()
    except Exception:
        pass
    _context = None
    _browser = None
    _pw = None


def _get_context(headless: bool = True):
    """Get or create a shared Playwright browser context."""
    global _browser, _context, _pw

    # Validate liveness — if context exists but browser is dead, reset
    if _context is not None:
        try:
            # Probe: create and immediately close a page to verify connection
            _p = _context.new_page()
            _p.close()
        except Exception:
            logger.warning("Stale browser context detected, resetting...")
            _reset_browser()

    if _context is not None:
        return _context

    from playwright.sync_api import sync_playwright

    _pw = sync_playwright().start()
    _browser = _pw.chromium.launch(headless=headless)
    _context = _browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 720},
    )
    atexit.register(close)
    return _context


def close():
    """Clean up browser resources."""
    global _browser, _context, _pw
    try:
        if _context:
            _context.close()
    except Exception:
        pass
    _context = None
    try:
        if _browser:
            _browser.close()
    except Exception:
        pass
    _browser = None
    try:
        if _pw:
            _pw.stop()
    except Exception:
        pass
    _pw = None


@_retry(max_attempts=2)
def search(query: str, max_pages: int = 1) -> list[dict]:
    """Search PhilGEPS open opportunities.

    Args:
        query: Simple keyword search (use single words, not phrases)
        max_pages: Number of result pages to scrape (20 results/page)

    Returns:
        List of notice dicts with: ref_no, title, agency, category,
        area_of_delivery, posted_date, closing_date, url
    """
    ctx = _get_context()
    page = ctx.new_page()

    try:
        # Load search page — starts in "View By Category" mode
        _rate_limit()
        page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=30000)

        # Click "Search" link to switch to search mode (ASP.NET __doPostBack)
        # The search box only appears after this postback
        search_link = page.locator('a:has-text("Search")').first
        search_link.click()
        page.wait_for_load_state("domcontentloaded")

        # Wait for search input to appear
        search_input = page.locator('#txtKeyword')
        search_input.wait_for(state="visible", timeout=10000)
        search_input.fill(query)

        # Click the search button and wait for results
        page.locator('#btnSearch').click()
        page.wait_for_load_state("domcontentloaded")
        page.locator('table tr td').first.wait_for(state="visible", timeout=15000)

        results = []
        for page_num in range(1, max_pages + 1):
            results.extend(_parse_search_results(page))
            logger.info(f"Page {page_num}: {len(results)} total results so far")

            if page_num < max_pages:
                # Navigate to next page
                try:
                    next_link = page.locator('a:has-text("<Next>")')
                    if next_link.count() > 0:
                        next_link.click()
                        page.wait_for_load_state("domcontentloaded")
                    else:
                        break
                except Exception:
                    break

        return results

    finally:
        page.close()


def _parse_search_results(page) -> list[dict]:
    """Parse the search results table from the current page."""
    results = []

    # Results are in table rows after the header row
    # Structure: row number | publish date | closing date | title (with link)
    rows = page.locator('table tr').all()

    for row in rows:
        cells = row.locator('td').all()
        if len(cells) < 4:
            continue

        # Check if first cell is a number (result row)
        first_text = cells[0].inner_text().strip()
        if not first_text.isdigit():
            continue

        # Extract data
        posted_date = cells[1].inner_text().strip()
        closing_date = cells[2].inner_text().strip()

        # Title cell contains a link + ", category, area"
        title_cell = cells[3]
        link = title_cell.locator('a').first
        if link.count() == 0:
            continue

        title = link.inner_text().strip()
        href = link.get_attribute('href') or ""

        # Extract refID from URL
        ref_match = re.search(r'refID=(\d+)', href)
        ref_no = ref_match.group(1) if ref_match else ""

        # Parse trailing text for category and area
        # Full text = title link + ", category, area"
        # Use the link element's text position to split reliably
        try:
            link_text = link.text_content().strip()
            full_text = title_cell.text_content().strip()
            idx = full_text.find(link_text)
            if idx >= 0:
                remainder = full_text[idx + len(link_text):].strip().lstrip(',').strip()
            else:
                remainder = ""
        except Exception:
            remainder = ""
        parts = [p.strip() for p in remainder.split(',')] if remainder else []
        category = parts[0] if len(parts) > 0 else ""
        area = parts[1] if len(parts) > 1 else ""

        # Build full detail URL
        detail_url = urljoin(page.url, href) if href else ""

        results.append({
            "ref_no": ref_no,
            "title": title,
            "agency": "",  # Real agency only available in detail page
            "notice_type": "",
            "category": category,
            "area_of_delivery": area,
            "posted_date": _normalize_date(posted_date),
            "closing_date": _normalize_date(closing_date),
            "approved_budget": 0,
            "description": "",
            "url": detail_url,
            "documents": [],
        })

    return results


@_retry(max_attempts=2)
def get_notice_detail(ref_id: str) -> dict:
    """Fetch full details for a procurement notice.

    Args:
        ref_id: PhilGEPS reference number (e.g., '12905086')

    Returns:
        Dict with full notice details including budget, procurement mode, etc.
    """
    ctx = _get_context()
    page = ctx.new_page()

    try:
        url = f"{DETAIL_URL}?menuIndex=3&refID={ref_id}&highlight=true"
        _rate_limit()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.locator('table tr td').first.wait_for(state="visible", timeout=10000)

        detail = {"ref_no": ref_id, "url": url}

        # Parse key-value rows from the detail table
        rows = page.locator('table tr').all()
        for row in rows:
            cells = row.locator('td').all()
            if len(cells) < 2:
                continue

            label = cells[0].inner_text().strip().rstrip(':')
            value = cells[1].inner_text().strip()

            field_map = {
                "Reference Number": "ref_no",
                "Procuring Entity": "agency",
                "Title": "title",
                "Area of Delivery": "area_of_delivery",
                "Solicitation Number": "solicitation_no",
                "Procurement Mode": "notice_type",
                "Category": "category",
                "Approved Budget for the Contract": "budget_raw",
                "Classification": "classification",
                "Delivery Period": "delivery_period",
                "Contact Person": "contact_person",
                "Status": "status",
            }

            if label in field_map:
                detail[field_map[label]] = value

        # Parse budget
        budget_raw = detail.get("budget_raw", "")
        budget_match = re.search(r'PHP\s*([\d,]+(?:\.\d+)?)', budget_raw)
        if budget_match:
            detail["approved_budget"] = float(budget_match.group(1).replace(',', ''))
        else:
            detail["approved_budget"] = 0

        detail.pop("budget_raw", None)

        # Extract description from the full page text
        try:
            desc_section = page.locator('td:has-text("Description") + td, '
                                        'td:has-text("Item/s") + td').first
            detail["description"] = desc_section.inner_text().strip()[:500]
        except Exception:
            detail["description"] = ""

        return detail

    finally:
        page.close()


@_retry(max_attempts=2)
def search_awards(agency: str = "", max_pages: int = 1) -> list[dict]:
    """Fetch recent award notices.

    WARNING: PhilGEPS frequently changes markup. This parser supports multiple
    common column layouts and paginates when a "Next" control is available.

    Args:
        agency: Optional agency filter.
        max_pages: Number of pages to scrape.

    Returns:
        List of award dicts.
    """
    ctx = _get_context()
    page = ctx.new_page()

    try:
        _rate_limit()
        page.goto(AWARDS_URL, wait_until="domcontentloaded", timeout=60000)
        page.locator('table tr td').first.wait_for(state="visible", timeout=15000)

        pages_count = max(1, max_pages)
        agency_filter = agency.lower().strip() if agency else ""
        awards: list[dict] = []

        for page_num in range(1, pages_count + 1):
            page_awards = _parse_award_rows(page, fallback_agency=agency)
            if agency_filter:
                page_awards = [
                    a for a in page_awards
                    if agency_filter in a.get("agency", "").lower()
                ]
            awards.extend(page_awards)

            if page_num >= pages_count:
                break
            if not _go_to_next_results_page(page):
                break

        # De-duplicate across pages/retries
        deduped: list[dict] = []
        seen: set[tuple] = set()
        for award in awards:
            key = (
                award.get("ref_no", ""),
                award.get("project_title", ""),
                award.get("agency", ""),
                award.get("supplier", ""),
                award.get("award_date", ""),
                float(award.get("award_amount", 0) or 0),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(award)

        return deduped

    finally:
        page.close()


def _parse_award_rows(page, fallback_agency: str = "") -> list[dict]:
    """Parse visible rows from the recent awards table.

    Supports both common layouts observed in PhilGEPS:
    - number | date | title | supplier | amount
    - number | date | title | agency | supplier | amount
    """
    awards: list[dict] = []
    rows = page.locator("table tr").all()

    for row in rows:
        cells = row.locator("td").all()
        if len(cells) < 5:
            continue

        first_text = cells[0].inner_text().strip()
        if not first_text.isdigit():
            continue

        project_title = cells[2].inner_text().strip() if len(cells) > 2 else ""
        award_date = _normalize_date(cells[1].inner_text().strip()) if len(cells) > 1 else ""

        # Layout A: number|date|title|supplier|amount
        # Layout B: number|date|title|agency|supplier|amount
        if len(cells) >= 6:
            parsed_agency = cells[3].inner_text().strip()
            supplier = cells[4].inner_text().strip()
            amount_text = cells[5].inner_text().strip()
        else:
            parsed_agency = ""
            supplier = cells[3].inner_text().strip()
            amount_text = cells[4].inner_text().strip()

        award = {
            "ref_no": "",
            "project_title": project_title,
            "agency": parsed_agency or fallback_agency or "UNKNOWN",
            "supplier": supplier,
            "award_amount": _parse_amount(amount_text),
            "award_date": award_date,
            "approved_budget": 0,
            "bid_type": "",
            "url": "",
        }

        # Try to extract ref and URL from title link
        try:
            link = cells[2].locator("a").first
            href = link.get_attribute("href") or ""
            ref_match = re.search(r"refID=(\d+)", href)
            if ref_match:
                award["ref_no"] = ref_match.group(1)
            if href:
                award["url"] = urljoin(getattr(page, "url", ""), href)
        except Exception:
            pass

        awards.append(award)

    return awards


def _first_results_row_signature(page) -> str:
    """Return a compact signature for the first data row in the current table."""
    rows = page.locator("table tr").all()
    for row in rows:
        cells = row.locator("td").all()
        if len(cells) < 3:
            continue
        first_text = cells[0].inner_text().strip()
        if not first_text.isdigit():
            continue
        c1 = cells[1].inner_text().strip() if len(cells) > 1 else ""
        c2 = cells[2].inner_text().strip() if len(cells) > 2 else ""
        return f"{first_text}|{c1}|{c2}"
    return ""


def _go_to_next_results_page(page) -> bool:
    """Click a likely pagination 'Next' control and verify the page changed."""
    next_selectors = [
        'a:has-text("<Next>")',
        'a:has-text("Next")',
        'a[title="Next"]',
        'a[aria-label="Next"]',
    ]

    before = _first_results_row_signature(page)
    saw_next_control = False
    errors: list[str] = []

    for selector in next_selectors:
        locator = page.locator(selector).first
        if locator.count() == 0:
            continue

        saw_next_control = True
        try:
            _rate_limit()
            locator.click()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(500)
            after = _first_results_row_signature(page)
            if after and after != before:
                return True
        except Exception as e:
            errors.append(f"{selector}: {e}")

    if saw_next_control and errors:
        raise RuntimeError(
            "Found pagination controls but failed to navigate to next awards page: "
            + " | ".join(errors)
        )

    return False


@_retry(max_attempts=2)
def list_agencies(
    max_pages: int = 1,
    progress_callback: Callable[[int, int, int], None] | None = None,
) -> list[dict]:
    """List procuring entities from the View By Agency page.

    Args:
        max_pages: Number of agency result pages to parse.
        progress_callback: Optional callback(current_page, total_pages, total_rows).

    Returns:
        Agency rows with rank, name, and opportunity_count.
    """
    ctx = _get_context()
    page = ctx.new_page()

    try:
        _rate_limit()
        page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=30000)

        agency_link = page.locator('a:has-text("View By Agency")').first
        agency_link.click()
        page.wait_for_load_state("domcontentloaded")
        page.locator("#pgCtrlOpp_pageDropDownList").wait_for(state="visible", timeout=30000)

        agencies: list[dict] = []
        page_selector = page.locator("#pgCtrlOpp_pageDropDownList")
        page_values = page.locator("#pgCtrlOpp_pageDropDownList option").evaluate_all(
            "opts => opts.map(o => o.value)"
        )
        total_pages = len(page_values)
        pages_count = min(max(1, max_pages), total_pages)

        for page_index in range(pages_count):
            expected_first_rank = str(page_values[page_index])
            if page_index > 0:
                _select_agency_page(page, page_selector, expected_first_rank)

            agencies.extend(_parse_agency_rows(page))
            if progress_callback is not None:
                progress_callback(page_index + 1, pages_count, len(agencies))

        deduped: list[dict] = []
        seen: set[tuple[int, str]] = set()
        for agency in agencies:
            key = (agency["rank"], agency["name"])
            if key in seen:
                continue
            seen.add(key)
            deduped.append(agency)

        return deduped

    finally:
        page.close()


def _select_agency_page(page, page_selector, expected_first_rank: str) -> None:
    """Navigate to a specific agency results page by its first rank value."""
    last_err = None
    for _attempt in range(5):
        try:
            _rate_limit()
            page_selector.select_option(value=expected_first_rank)
            page.wait_for_function(
                "expected => {"
                "  const rows = Array.from(document.querySelectorAll('table tr'));"
                "  for (const row of rows) {"
                "    const cells = row.querySelectorAll('td');"
                "    if (cells.length >= 3) {"
                "      const rank = (cells[0].innerText || '').trim();"
                "      const count = (cells[2].innerText || '').trim();"
                "      if (/^\\d+$/.test(rank) && /^\\d+$/.test(count)) {"
                "        return rank === expected;"
                "      }"
                "    }"
                "  }"
                "  return false;"
                "}",
                arg=expected_first_rank,
                timeout=60000,
            )
            return
        except Exception as e:
            last_err = e
            time.sleep(1)
    raise RuntimeError(f"Failed to load agency page starting at rank {expected_first_rank}: {last_err}")


def _parse_agency_rows(page) -> list[dict]:
    """Parse visible rows from the agency table on the current page."""
    agencies: list[dict] = []
    rows = page.locator("table tr").all()
    for row in rows:
        cells = row.locator("td").all()
        if len(cells) < 3:
            continue

        rank = cells[0].inner_text().strip()
        name = cells[1].inner_text().strip()
        opportunity_count = cells[2].inner_text().strip()

        if not rank.isdigit():
            continue
        if not name or name.lower() == "agency":
            continue
        if not opportunity_count.isdigit():
            continue

        agencies.append({
            "rank": int(rank),
            "name": name,
            "opportunity_count": int(opportunity_count),
        })

    return agencies


def _normalize_date(date_str: str) -> str:
    """Convert DD/MM/YYYY to ISO date string."""
    if not date_str:
        return ""
    # Remove time portion if present
    date_str = date_str.split(' ')[0]
    parts = date_str.split('/')
    if len(parts) == 3:
        try:
            day, month, year = parts
            day_i, month_i = int(day), int(month)
            if not (1 <= day_i <= 31 and 1 <= month_i <= 12):
                logger.warning(f"Unusual date values in '{date_str}': day={day_i}, month={month_i}")
                return date_str  # Don't produce impossible ISO dates
            return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        except (ValueError, IndexError):
            logger.warning(f"Failed to parse date: '{date_str}'")
    return date_str


def _parse_amount(text: str) -> float:
    """Parse a currency amount string to float."""
    text = re.sub(r'[^\d.]', '', text)
    try:
        return float(text) if text else 0.0
    except ValueError:
        return 0.0
