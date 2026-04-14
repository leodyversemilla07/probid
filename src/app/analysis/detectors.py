"""Analysis engine — overpricing detection, repeat awardees, contract splitting."""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import Any


def find_repeat_awardees(conn: sqlite3.Connection, min_count: int = 3) -> list[dict]:
    """Find suppliers who win contracts frequently.

    High award frequency across multiple agencies can indicate:
    - Legitimate preferred suppliers
    - Bid rigging / collusion
    - Shell company networks
    """
    rows = conn.execute(
        """
        SELECT supplier,
               COUNT(*) as award_count,
               COUNT(DISTINCT agency) as agency_count,
               SUM(award_amount) as total_value
        FROM awards
        WHERE supplier != ''
        GROUP BY LOWER(TRIM(supplier))
        HAVING award_count >= ?
        ORDER BY award_count DESC
    """,
        (min_count,),
    ).fetchall()

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
    to stay below procurement threshold limits.

    Heuristic: Same agency, similar titles, close dates, amounts just under thresholds.
    """
    thresholds = [
        50_000,
        500_000,
        2_000_000,
    ]

    rows = conn.execute(
        """
        SELECT * FROM awards
        WHERE agency LIKE ?
        ORDER BY award_date, project_title
    """,
        (f"%{agency}%",),
    ).fetchall()

    awards = [dict(r) for r in rows]
    suspicious = []

    groups = _group_by_title_similarity(awards, min_overlap=0.5)

    for _, group in groups.items():
        if len(group) < 2:
            continue

        for threshold in thresholds:
            near_threshold = [
                a for a in group if threshold * 0.7 <= a.get("award_amount", 0) < threshold
            ]

            if len(near_threshold) < 2:
                continue

            dated = []
            for a in near_threshold:
                try:
                    dt = datetime.strptime(a.get("award_date", ""), "%Y-%m-%d")
                    dated.append((a, dt))
                except (ValueError, TypeError):
                    pass

            if len(dated) < 2:
                continue

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
                suspicious.append(
                    {
                        "pattern": f"{len(cluster_contracts)} contracts near PHP {threshold:,} threshold",
                        "contracts": cluster_contracts,
                        "total_value": total,
                        "threshold": threshold,
                    }
                )

    return suspicious


def _group_by_title_similarity(awards: list[dict], min_overlap: float = 0.5) -> dict[str, list]:
    """Group awards by title token overlap."""
    groups: dict[str, list] = {}

    for a in awards:
        title = a.get("project_title", "").upper()
        tokens = set(title.split())

        if not tokens:
            groups.setdefault("__untitled__", []).append(a)
            continue

        matched_key = None
        best_overlap = 0.0

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
    """Analyze a supplier's network — who they compete against."""
    agencies = conn.execute(
        """
        SELECT DISTINCT agency FROM awards WHERE supplier LIKE ?
    """,
        (f"%{supplier}%",),
    ).fetchall()
    agency_list = [r["agency"] for r in agencies]

    if not agency_list:
        return {"supplier": supplier, "connections": []}

    placeholders = ",".join("?" * len(agency_list))
    competitors = conn.execute(
        f"""
        SELECT supplier, COUNT(DISTINCT agency) as shared_agencies,
               GROUP_CONCAT(DISTINCT agency) as agency_list
        FROM awards
        WHERE agency IN ({placeholders})
          AND supplier NOT LIKE ?
        GROUP BY LOWER(TRIM(supplier))
        HAVING shared_agencies >= 2
        ORDER BY shared_agencies DESC
        LIMIT 20
    """,
        [*agency_list, f"%{supplier}%"],
    ).fetchall()

    return {
        "supplier": supplier,
        "agencies_served": agency_list,
        "competitors": [dict(c) for c in competitors],
    }


def _build_finding(
    code: str,
    title: str,
    severity: str,
    confidence: str,
    summary: str,
    evidence: dict[str, Any],
    caveat: str,
) -> dict[str, Any]:
    return {
        "reason_code": code,
        "title": title,
        "severity": severity,
        "confidence": confidence,
        "summary": summary,
        "evidence": evidence,
        "caveat": caveat,
    }


def analyze_probe_findings(
    conn: sqlite3.Connection,
    query: str = "",
    agency: str = "",
    pages_scanned: int = 1,
    split_gap_days: int = 30,
    repeat_min_count: int = 3,
) -> dict[str, Any]:
    """Build reason-coded findings for probe summary output.

    Returns summary + findings + risk_map for rendering and JSON mode.
    """
    findings: list[dict[str, Any]] = []

    base_notices_sql = "SELECT * FROM notices WHERE 1=1"
    base_awards_sql = "SELECT * FROM awards WHERE 1=1"
    notice_params: list[Any] = []
    award_params: list[Any] = []

    if query:
        q = f"%{query}%"
        base_notices_sql += " AND (title LIKE ? OR category LIKE ? OR description LIKE ? OR ref_no LIKE ?)"
        notice_params.extend([q, q, q, q])
        base_awards_sql += " AND (project_title LIKE ? OR supplier LIKE ? OR ref_no LIKE ?)"
        award_params.extend([q, q, q])

    if agency:
        a = f"%{agency}%"
        base_notices_sql += " AND agency LIKE ?"
        base_awards_sql += " AND agency LIKE ?"
        notice_params.append(a)
        award_params.append(a)

    notices = [dict(r) for r in conn.execute(base_notices_sql, notice_params).fetchall()]
    awards = [dict(r) for r in conn.execute(base_awards_sql, award_params).fetchall()]

    records_scanned = len(notices) + len(awards)
    agencies_touched = len({*(n.get("agency", "") for n in notices), *(a.get("agency", "") for a in awards)} - {""})
    total_known_value = sum((a.get("award_amount", 0) or 0) for a in awards)

    # R7: sparse data warning
    if len(awards) < 5 and len(notices) < 10:
        findings.append(
            _build_finding(
                "R7",
                "Sparse dataset warning",
                "medium",
                "high",
                "Limited local data may reduce detection reliability.",
                {
                    "notice_count": len(notices),
                    "award_count": len(awards),
                },
                "Run broader search/pages and refresh cache before drawing conclusions.",
            )
        )

    # R1: repeat supplier concentration
    repeat_rows = find_repeat_awardees(conn, min_count=repeat_min_count)
    for row in repeat_rows[:5]:
        supplier = row.get("supplier", "")
        award_count = int(row.get("award_count", 0) or 0)
        agency_count = int(row.get("agency_count", 0) or 0)
        confidence = "high" if award_count >= 6 and agency_count >= 2 else "medium"
        severity = "high" if award_count >= 8 else "medium"
        findings.append(
            _build_finding(
                "R1",
                "Repeat supplier concentration",
                severity,
                confidence,
                f"{supplier} won {award_count} awards across {agency_count} agencies.",
                {
                    "supplier": supplier,
                    "award_count": award_count,
                    "agency_count": agency_count,
                    "total_value": row.get("total_value", 0) or 0,
                },
                "High frequency can be legitimate for specialized suppliers; verify market depth.",
            )
        )

    # R2: near-ABC awards pattern
    near_rows = conn.execute(
        """
        SELECT agency, supplier,
               COUNT(*) AS hit_count,
               AVG(CASE WHEN approved_budget > 0 THEN (award_amount / approved_budget) * 100 END) AS avg_utilization,
               SUM(award_amount) AS total_amount
        FROM awards
        WHERE approved_budget > 0
          AND award_amount > 0
          AND (award_amount / approved_budget) BETWEEN 0.97 AND 1.00
        GROUP BY LOWER(TRIM(agency)), LOWER(TRIM(supplier))
        HAVING hit_count >= 2
        ORDER BY hit_count DESC
        LIMIT 5
    """
    ).fetchall()

    for row in near_rows:
        hit_count = int(row["hit_count"] or 0)
        confidence = "high" if hit_count >= 4 else "medium"
        findings.append(
            _build_finding(
                "R2",
                "Near-ABC award pattern",
                "medium",
                confidence,
                f"{row['supplier']} in {row['agency']} has {hit_count} awards near 97-100% of ABC.",
                {
                    "agency": row["agency"],
                    "supplier": row["supplier"],
                    "hit_count": hit_count,
                    "avg_utilization_pct": round(float(row["avg_utilization"] or 0), 2),
                    "total_amount": row["total_amount"] or 0,
                },
                "Near-ABC awards may still occur in competitive markets with tight costing.",
            )
        )

    # R3: potential split contracts
    agencies_for_split = [agency] if agency else [r["agency"] for r in conn.execute("SELECT DISTINCT agency FROM awards WHERE agency != '' LIMIT 15").fetchall()]
    split_hits = 0
    for agency_name in agencies_for_split:
        split_results = detect_split_contracts(conn, agency_name, max_gap_days=split_gap_days)
        for split in split_results[:2]:
            split_hits += 1
            contract_count = len(split.get("contracts", []))
            findings.append(
                _build_finding(
                    "R3",
                    "Potential contract splitting",
                    "high" if contract_count >= 3 else "medium",
                    "medium",
                    f"{agency_name} has {contract_count} similar contracts clustered near threshold.",
                    {
                        "agency": agency_name,
                        "threshold": split.get("threshold"),
                        "contract_count": contract_count,
                        "total_value": split.get("total_value", 0),
                        "sample_refs": [c.get("ref_no") for c in split.get("contracts", [])[:5]],
                    },
                    "Could reflect phased procurement or recurring needs; validate with PPMP/APP context.",
                )
            )
        if split_hits >= 5:
            break

    # R4: procurement mode outlier frequency
    mode_rows = conn.execute(
        """
        SELECT COALESCE(NULLIF(TRIM(notice_type), ''), 'UNKNOWN') AS notice_type,
               COUNT(*) AS cnt
        FROM notices
        GROUP BY notice_type
        ORDER BY cnt DESC
    """
    ).fetchall()
    total_mode = sum(int(r["cnt"] or 0) for r in mode_rows)
    if total_mode >= 10 and mode_rows:
        top_mode = mode_rows[0]
        share = (int(top_mode["cnt"]) / total_mode) * 100
        if share >= 70:
            findings.append(
                _build_finding(
                    "R4",
                    "Procurement mode outlier",
                    "medium",
                    "medium",
                    f"Mode '{top_mode['notice_type']}' accounts for {share:.1f}% of notices.",
                    {
                        "notice_type": top_mode["notice_type"],
                        "mode_count": int(top_mode["cnt"]),
                        "total_notices": total_mode,
                        "share_pct": round(share, 2),
                    },
                    "Dataset scope and category mix can skew mode-share ratios.",
                )
            )

    # R5: abnormal category price spread
    price_rows = find_price_anomalies(conn, category=query)
    for row in price_rows[:3]:
        min_price = float(row.get("min_price", 0) or 0)
        max_price = float(row.get("max_price", 0) or 0)
        if min_price <= 0:
            continue
        spread = ((max_price - min_price) / min_price) * 100
        if spread < 200:
            continue
        findings.append(
            _build_finding(
                "R5",
                "Abnormal budget spread",
                "medium",
                "medium",
                f"Category '{row.get('category', '')}' shows {spread:.0f}% budget spread.",
                {
                    "category": row.get("category", ""),
                    "min_price": min_price,
                    "max_price": max_price,
                    "sample_count": int(row.get("sample_count", 0) or 0),
                    "spread_pct": round(spread, 2),
                },
                "Different technical specs can legitimately widen budget spread.",
            )
        )

    # R6: single-agency dependence risk (supplier)
    dependence_rows = conn.execute(
        """
        SELECT supplier,
               COUNT(*) AS award_count,
               COUNT(DISTINCT agency) AS agency_count,
               SUM(award_amount) AS total_value,
               MIN(agency) AS agency
        FROM awards
        WHERE supplier != ''
        GROUP BY LOWER(TRIM(supplier))
        HAVING award_count >= 3 AND agency_count = 1
        ORDER BY total_value DESC
        LIMIT 5
    """
    ).fetchall()
    for row in dependence_rows:
        findings.append(
            _build_finding(
                "R6",
                "Single-agency dependence risk",
                "low",
                "medium",
                f"{row['supplier']} has {row['award_count']} awards from only one agency ({row['agency']}).",
                {
                    "supplier": row["supplier"],
                    "agency": row["agency"],
                    "award_count": int(row["award_count"] or 0),
                    "total_value": row["total_value"] or 0,
                },
                "May be normal for niche vendors with specialized contracts.",
            )
        )

    # R8: beneficial ownership transparency gap
    findings.append(
        _build_finding(
            "R8",
            "Beneficial ownership disclosure gap",
            "low",
            "high",
            "Current local dataset does not include beneficial ownership fields for suppliers.",
            {
                "available_tables": ["notices", "awards"],
                "field_gap": "beneficial_owner",
            },
            "Need external SEC/ownership datasets to operationalize this check.",
        )
    )

    severity_rank = {"high": 3, "medium": 2, "low": 1}
    confidence_rank = {"high": 3, "medium": 2, "low": 1}
    findings.sort(
        key=lambda f: (
            severity_rank.get(f.get("severity", "low"), 1),
            confidence_rank.get(f.get("confidence", "low"), 1),
        ),
        reverse=True,
    )

    risk_map: dict[str, int] = {}
    for f in findings:
        code = f["reason_code"]
        risk_map[code] = risk_map.get(code, 0) + 1

    return {
        "metadata": {
            "query": query,
            "agency": agency,
            "pages_scanned": pages_scanned,
            "generated_at": datetime.utcnow().isoformat() + "Z",
        },
        "summary": {
            "records_scanned": records_scanned,
            "notice_count": len(notices),
            "award_count": len(awards),
            "agencies_touched": agencies_touched,
            "total_known_value": total_known_value,
            "finding_count": len(findings),
        },
        "risk_map": risk_map,
        "findings": findings,
    }
