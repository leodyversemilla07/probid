"""Search-oriented CLI commands."""

from __future__ import annotations

import json

import click

from app.data import cache
from app.sources import philgeps as geps
from app.ui import display


def register_search_commands(cli: click.Group) -> None:
    """Register search and detail commands."""

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
        pages_count = max(1, pages)

        with cache.connection() as conn:
            if cache_only:
                results = cache.search_notices(conn, query=query, agency=agency)
                display.show_notices(results, query)
                return

            display.info(f'Searching PhilGEPS for "{query}"...')
            try:
                results = geps.search(query, max_pages=pages_count)
            except Exception as e:
                display.error(f"Scraping failed: {e}")
                display.info("Falling back to local cache...")
                results = cache.search_notices(conn, query=query, agency=agency)
                display.show_notices(results, query)
                geps.close()
                return

            for result in results:
                cache.upsert_notice(conn, result)

            if agency:
                agency_term = agency.lower()
                results = [
                    result for result in results
                    if agency_term in result.get("agency", "").lower()
                    or agency_term in result.get("area_of_delivery", "").lower()
                ]

            display.show_notices(results, query)

            if detail and results:
                display.info("Fetching details for top results...")
                for result in results[:5]:
                    if result.get("ref_no"):
                        try:
                            detail_result = geps.get_notice_detail(result["ref_no"])
                            merged = {**result, **detail_result}
                            merged["documents"] = detail_result.get(
                                "documents", result.get("documents", [])
                            )
                            cache.upsert_notice(conn, merged)
                            display.show_notice_detail(merged)
                        except Exception as e:
                            display.error(
                                f"Detail fetch failed for {result['ref_no']}: {e}"
                            )

            geps.close()

    @cli.command()
    @click.argument("ref_id")
    @click.option("--force", "-f", is_flag=True, help="Re-fetch even if cached")
    def detail(ref_id: str, force: bool):
        """Fetch full details for a procurement notice by reference ID.

        REF_ID is the PhilGEPS reference number (e.g., 12905086).
        """
        with cache.connection() as conn:
            if not force:
                cached = conn.execute(
                    "SELECT * FROM notices WHERE ref_no = ?", (ref_id,)
                ).fetchone()
                if cached:
                    display.info("Showing cached data (use --force to re-fetch)")
                    detail_data = dict(cached)
                    try:
                        detail_data["documents"] = json.loads(detail_data.get("documents", "[]"))
                    except (json.JSONDecodeError, TypeError):
                        detail_data["documents"] = []
                    display.show_notice_detail(detail_data)
                    return

            display.info(f"Fetching details for {ref_id}...")
            try:
                detail_data = geps.get_notice_detail(ref_id)
                cache.upsert_notice(conn, detail_data)
                display.show_notice_detail(detail_data)
            except Exception as e:
                display.error(f"Failed to fetch: {e}")

            geps.close()

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
