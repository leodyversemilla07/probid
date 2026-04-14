"""Analysis engine — overpricing detection, repeat awardees, contract splitting."""

from __future__ import annotations

import sqlite3


def find_repeat_awardees(conn: sqlite3.Connection, min_count: int = 3) -> list[dict]:
    """Find suppliers who win contracts frequently.

    High award frequency across multiple agencies can indicate:
    - Legitimate preferred suppliers
    - Bid rigging / collusion
    - Shell company networks
    """
    rows = conn.execute("""
        SELECT supplier,
               COUNT(*) as award_count,
               COUNT(DISTINCT agency) as agency_count,
               SUM(award_amount) as total_value
        FROM awards
        WHERE supplier != ''
        GROUP BY LOWER(TRIM(supplier))
        HAVING award_count >= ?
        ORDER BY award_count DESC
    """, (min_count,)).fetchall()

    return [dict(r) for r in rows]


def find_price_anomalies(conn: sqlite3.Connection, category: str = "") -> list[dict]:
    """Compare similar items across agencies for pricing discrepancies.

    Uses approved budget from notices as a proxy for benchmarking.
    Large budget spreads for similar items can indicate:
    - Overpricing / over-specification
    - Different product tiers (legitimate)
    - Kickback schemes
    """
    sql = """
        SELECT category, MIN(approved_budget) as min_price,
               MAX(approved_budget) as max_price,
               AVG(approved_budget) as avg_price,
               COUNT(*) as sample_count
        FROM notices
        WHERE approved_budget > 0 AND category != ''
    """
    params = []
    if category:
        sql += " AND (category LIKE ? OR title LIKE ?)"
        params.extend([f"%{category}%", f"%{category}%"])

    sql += """
        GROUP BY LOWER(TRIM(category))
        HAVING sample_count >= 2
        ORDER BY (max_price - min_price) / NULLIF(min_price, 0) DESC
    """

    rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def detect_split_contracts(
    conn: sqlite3.Connection,
    agency: str,
    max_gap_days: int = 30,
) -> list[dict]:
    """Detect potential contract splitting.

    Contract splitting = breaking one big purchase into multiple small ones
    to stay below procurement threshold limits (e.g., PHP 500K for shopping).

    Heuristic: Same agency, similar titles, close dates, amounts just under thresholds.
    """
    from datetime import datetime

    thresholds = [
        50_000,    # Shopping
        500_000,   # Small value procurement
        2_000_000, # Competitive bidding threshold (varies)
    ]

    rows = conn.execute("""
        SELECT * FROM awards
        WHERE agency LIKE ?
        ORDER BY award_date, project_title
    """, (f"%{agency}%",)).fetchall()

    awards = [dict(r) for r in rows]
    suspicious = []

    # Group by token overlap (more robust than first-N-words)
    groups = _group_by_title_similarity(awards, min_overlap=0.5)

    for key, group in groups.items():
        if len(group) < 2:
            continue

        # Check if amounts are clustered just under thresholds
        for threshold in thresholds:
            near_threshold = [
                a for a in group
                if threshold * 0.7 <= a.get("award_amount", 0) < threshold
            ]

            if len(near_threshold) < 2:
                continue

            # Parse dates
            dated = []
            for a in near_threshold:
                try:
                    dt = datetime.strptime(a.get("award_date", ""), "%Y-%m-%d")
                    dated.append((a, dt))
                except (ValueError, TypeError):
                    pass

            if len(dated) < 2:
                continue

            # Sliding window: sort by date, find contiguous clusters within max_gap_days
            dated.sort(key=lambda x: x[1])
            clusters = []
            current = [dated[0]]
            for i in range(1, len(dated)):
                gap = (dated[i][1] - current[-1][1]).days
                if gap <= max_gap_days:
                    current.append(dated[i])
                else:
                    if len(current) >= 2:
                        clusters.append(current)
                    current = [dated[i]]
            if len(current) >= 2:
                clusters.append(current)

            for cluster in clusters:
                cluster_contracts = [a for a, _ in cluster]
                total = sum(a.get("award_amount", 0) for a in cluster_contracts)
                suspicious.append({
                    "pattern": f"{len(cluster_contracts)} contracts near PHP {threshold:,} threshold",
                    "contracts": cluster_contracts,
                    "total_value": total,
                    "threshold": threshold,
                })

    return suspicious


def _group_by_title_similarity(awards: list[dict], min_overlap: float = 0.5) -> dict[str, list]:
    """Group awards by title token overlap.

    Two awards are grouped together if they share >= min_overlap of their tokens.
    Uses the award with the most tokens as the group key.
    """
    groups: dict[str, list] = {}

    for a in awards:
        title = a.get("project_title", "").upper()
        tokens = set(title.split())

        if not tokens:
            # Group empty titles under a special key
            groups.setdefault("__untitled__", []).append(a)
            continue

        matched_key = None
        best_overlap = 0

        for key in groups:
            key_tokens = set(key.split())
            if not key_tokens:
                continue
            overlap = len(tokens & key_tokens) / min(len(tokens), len(key_tokens))
            if overlap >= min_overlap and overlap > best_overlap:
                matched_key = key
                best_overlap = overlap

        if matched_key:
            groups[matched_key].append(a)
        else:
            groups[title] = [a]

    return groups


def network_analysis(conn: sqlite3.Connection, supplier: str) -> dict:
    """Analyze a supplier's network — who they compete against, who they share addresses with.

    This is basic heuristic analysis. Real shell company detection needs
    SEC registration data cross-referencing.
    """
    # Get agencies this supplier serves
    agencies = conn.execute("""
        SELECT DISTINCT agency FROM awards WHERE supplier LIKE ?
    """, (f"%{supplier}%",)).fetchall()
    agency_list = [r["agency"] for r in agencies]

    if not agency_list:
        return {"supplier": supplier, "connections": []}

    # Find other suppliers who serve the same agencies
    placeholders = ",".join("?" * len(agency_list))
    competitors = conn.execute(f"""
        SELECT supplier, COUNT(DISTINCT agency) as shared_agencies,
               GROUP_CONCAT(DISTINCT agency) as agency_list
        FROM awards
        WHERE agency IN ({placeholders})
          AND supplier NOT LIKE ?
        GROUP BY LOWER(TRIM(supplier))
        HAVING shared_agencies >= 2
        ORDER BY shared_agencies DESC
        LIMIT 20
    """, [*agency_list, f"%{supplier}%"]).fetchall()

    return {
        "supplier": supplier,
        "agencies_served": agency_list,
        "competitors": [dict(c) for c in competitors],
    }
