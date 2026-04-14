"""Search-oriented CLI commands."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import click

from app import analysis
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
                    result
                    for result in results
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
                            display.error(f"Detail fetch failed for {result['ref_no']}: {e}")

            geps.close()

    @cli.command()
    @click.argument("query")
    @click.option("--agency", "-a", default="", help="Optional agency filter")
    @click.option("--pages", "-p", default=1, help="Pages to scrape if live fetch is needed")
    @click.option("--why", is_flag=True, help="Show evidence and caveats for each finding")
    @click.option("--json", "as_json", is_flag=True, help="Emit machine-readable JSON")
    @click.option("--cache-only", is_flag=True, help="Use local cache only (no live scraping)")
    def probe(query: str, agency: str, pages: int, why: bool, as_json: bool, cache_only: bool):
        """Probe procurement data with summary-first, reason-coded risk findings."""
        pages_count = max(1, pages)

        with cache.connection() as conn:
            if not cache_only:
                display.info(f'Probing PhilGEPS for "{query}" (pages={pages_count})...')
                try:
                    notices = geps.search(query, max_pages=pages_count)
                    for notice in notices:
                        cache.upsert_notice(conn, notice)
                except Exception as e:
                    display.error(f"Live fetch failed: {e}")
                    display.info("Continuing with local cache...")
                finally:
                    geps.close()

            result = analysis.analyze_probe_findings(
                conn,
                query=query,
                agency=agency,
                pages_scanned=pages_count,
            )

            if as_json:
                click.echo(json.dumps(result, indent=2, ensure_ascii=False))
                return

            display.show_probe_summary(result)
            display.show_probe_findings(result.get("findings", []), show_why=why)
            display.show_probe_next_checks(result)

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
    @click.option("--pages", "-p", default=1, help="Agency result pages to fetch")
    @click.option("--all", "fetch_all", is_flag=True, help="Fetch all agency pages")
    @click.option("--output", "-o", type=click.Path(path_type=Path), help="Save results to CSV")
    def agencies(pages: int, fetch_all: bool, output: Path | None):
        """List procuring entities on PhilGEPS.

        By default, fetches the first page only. Use --pages or --all for more.
        """
        pages_count = 10_000 if fetch_all else max(1, pages)
        display.info(
            "Fetching agency list from PhilGEPS..."
            + (" all pages" if fetch_all else f" {pages_count} page(s)")
        )

        def on_progress(current_page: int, total_pages: int, total_rows: int) -> None:
            display.info(f"Fetched page {current_page}/{total_pages} ({total_rows} rows)")

        try:
            agency_list = geps.list_agencies(
                max_pages=pages_count,
                progress_callback=on_progress if fetch_all or pages_count > 1 else None,
            )

            if output is not None:
                output.parent.mkdir(parents=True, exist_ok=True)
                with output.open("w", newline="", encoding="utf-8") as f:
                    writer = csv.DictWriter(
                        f,
                        fieldnames=["rank", "name", "opportunity_count"],
                    )
                    writer.writeheader()
                    writer.writerows(agency_list)
                display.success(f"Saved {len(agency_list)} agencies to {output}")

            if fetch_all and output is None and len(agency_list) > 100:
                display.info(
                    f"Showing first 100 of {len(agency_list)} agencies. "
                    "Use --output agencies.csv to save the full list."
                )
                display.show_agencies_list(agency_list[:100])
            else:
                display.show_agencies_list(agency_list)
        except Exception as e:
            display.error(f"Failed to fetch agencies: {e}")
        finally:
            geps.close()
