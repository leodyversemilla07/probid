"""probid CLI — Probe Philippine government procurement."""

from __future__ import annotations

import json

import click

from probid import cache, display, analyze
from probid.sources import philgeps as geps


@click.group()
@click.version_option("0.1.0", prog_name="probid")
def cli():
    """probid — Probe Philippine government procurement.

    Search procurement notices, track contract awards, and detect suspicious patterns.
    Data sourced from PhilGEPS (Philippine Government Electronic Procurement System).
    """
    pass


# ── Search ──

@cli.command()
@click.argument("query")
@click.option("--agency", "-a", help="Filter by agency name")
@click.option("--pages", "-p", default=1, help="Pages to scrape (20 results/page)")
@click.option("--detail", "-d", is_flag=True, help="Fetch full details for each result")
@click.option("--cache-only", is_flag=True, help="Only search local cache (no scraping)")
def search(query: str, agency: str, pages: int, detail: bool, cache_only: bool):
    """Search procurement notices by keyword.

    Use simple keywords (e.g., "laptop", "server", "consulting").
    PhilGEPS search works best with single words.
    """
    pages = max(1, pages)

    with cache.connection() as conn:
        if cache_only:
            results = cache.search_notices(conn, query=query, agency=agency)
            display.show_notices(results, query)
            return

        display.info(f'Searching PhilGEPS for "{query}"...')
        try:
            results = geps.search(query, max_pages=pages)
        except Exception as e:
            display.error(f"Scraping failed: {e}")
            display.info("Falling back to local cache...")
            results = cache.search_notices(conn, query=query, agency=agency)
            display.show_notices(results, query)
            geps.close()
            return

        # Cache all results (for future --cache-only searches)
        for r in results:
            cache.upsert_notice(conn, r)

        # Filter by agency if specified (post-scrape, since PhilGEPS doesn't support agency search)
        if agency:
            results = [
                r for r in results
                if agency.lower() in r.get("agency", "").lower()
                or agency.lower() in r.get("area_of_delivery", "").lower()
            ]

        display.show_notices(results, query)

        if detail and results:
            display.info("Fetching details for top results...")
            for r in results[:5]:
                if r.get("ref_no"):
                    try:
                        d = geps.get_notice_detail(r["ref_no"])
                        # Merge: detail fields override search, search fills gaps
                        merged = {**r, **d}
                        merged["documents"] = d.get("documents", r.get("documents", []))
                        cache.upsert_notice(conn, merged)
                        display.show_notice_detail(merged)
                    except Exception as e:
                        display.error(f"Detail fetch failed for {r['ref_no']}: {e}")

        geps.close()


# ── Detail ──

@cli.command()
@click.argument("ref_id")
@click.option("--force", "-f", is_flag=True, help="Re-fetch even if cached")
def detail(ref_id: str, force: bool):
    """Fetch full details for a procurement notice by reference ID.

    REF_ID is the PhilGEPS reference number (e.g., 12905086).
    """
    with cache.connection() as conn:
        # Check cache first (search by ref_no directly)
        if not force:
            cached = conn.execute(
                "SELECT * FROM notices WHERE ref_no = ?", (ref_id,)
            ).fetchone()
            if cached:
                display.info("Showing cached data (use --force to re-fetch)")
                d = dict(cached)
                try:
                    d["documents"] = json.loads(d.get("documents", "[]"))
                except (json.JSONDecodeError, TypeError):
                    d["documents"] = []
                display.show_notice_detail(d)
                return

        display.info(f"Fetching details for {ref_id}...")
        try:
            d = geps.get_notice_detail(ref_id)
            cache.upsert_notice(conn, d)
            display.show_notice_detail(d)
        except Exception as e:
            display.error(f"Failed to fetch: {e}")

        geps.close()


# ── Awards ──

@cli.command()
@click.option("--agency", "-a", help="Filter by agency name")
@click.option("--supplier", "-s", help="Filter by supplier name")
@click.option("--limit", "-n", default=50, help="Max results")
@click.option("--cache-only", is_flag=True, help="Only search local cache")
def awards(agency: str, supplier: str, limit: int, cache_only: bool):
    """List recent contract awards."""
    with cache.connection() as conn:
        if not cache_only and not supplier:
            display.info("Fetching recent awards from PhilGEPS...")
            try:
                geps_awards = geps.search_awards(agency=agency)
                for a in geps_awards:
                    cache.upsert_award(conn, a)
            except Exception as e:
                display.error(f"Scraping failed: {e}")

        results = cache.search_awards(conn, agency=agency, supplier=supplier, limit=limit)
        display.show_awards(results, agency=agency, supplier=supplier)

        if not cache_only:
            try:
                geps.close()
            except Exception:
                pass


# ── Supplier ──

@cli.command()
@click.argument("name")
def supplier(name: str):
    """Look up a supplier's profile and award history."""
    with cache.connection() as conn:
        stats = cache.get_supplier_stats(conn, name)
        display.show_supplier_stats(stats, name)

        awards_list = cache.search_awards(conn, supplier=name, limit=20)
        if awards_list:
            display.show_awards(awards_list, supplier=name)


# ── Agency ──

@cli.command()
@click.argument("name")
def agency(name: str):
    """Show procurement profile for a government agency."""
    with cache.connection() as conn:
        stats = cache.get_agency_stats(conn, name)
        display.show_agency_stats(stats, name)


# ── Overprice ──

@cli.command()
@click.argument("category", default="")
@click.option("--threshold", "-t", default=200, help="Price spread %% to flag")
def overprice(category: str, threshold: int):
    """Detect pricing anomalies across agencies.

    Compare similar items to find potential overpricing.
    CATEGORY can be partial (e.g., "laptop", "consulting").
    """
    with cache.connection() as conn:
        results = analyze.find_price_anomalies(conn, category=category)
        display.show_overprice_analysis(results, threshold=threshold)


# ── Repeat Awardees ──

@cli.command()
@click.option("--min-count", "-n", default=3, help="Minimum award count to flag")
def repeat(min_count: int):
    """Find suppliers with high award frequency (potential red flags)."""
    with cache.connection() as conn:
        awardees = analyze.find_repeat_awardees(conn, min_count=min_count)
        display.show_repeat_awardees(awardees)


# ── Network ──

@cli.command()
@click.argument("supplier_name")
def network(supplier_name: str):
    """Analyze a supplier's network — agencies, competitors."""
    with cache.connection() as conn:
        display.info(f"Analyzing network for {supplier_name}...")
        result = analyze.network_analysis(conn, supplier_name)
        display.show_network(result, supplier_name)


# ── Agencies List ──

@cli.command()
def agencies():
    """List all known procuring entities on PhilGEPS."""
    display.info("Fetching agency list from PhilGEPS...")
    try:
        agency_list = geps.list_agencies()
        display.show_agencies_list(agency_list)
    except Exception as e:
        display.error(f"Failed to fetch agencies: {e}")
    finally:
        geps.close()


# ── Split Contracts ──

@cli.command()
@click.argument("agency")
@click.option("--gap-days", default=30, help="Max days between related contracts")
def split(agency: str, gap_days: int):
    """Detect potential contract splitting for an agency."""
    with cache.connection() as conn:
        results = analyze.detect_split_contracts(conn, agency, gap_days)
        display.show_split_contracts(results, agency)


if __name__ == "__main__":
    cli()
