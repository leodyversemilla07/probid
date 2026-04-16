"""SQLite-backed cache for scraped data."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

DEFAULT_CACHE_DIR = Path.home() / ".probid"
DEFAULT_DB_NAME = "probid.db"


def get_cache_dir() -> Path:
    """Return cache directory, creating if needed."""
    cache_dir = Path(os.environ.get("PROBID_CACHE_DIR", DEFAULT_CACHE_DIR))
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Get a SQLite connection, creating tables if needed. Internal use — prefer connection()."""
    if db_path is None:
        db_path = str(get_cache_dir() / DEFAULT_DB_NAME)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    # Ensure schema exists for this specific database path.
    _ensure_tables(conn)
    return conn


@contextmanager
def connection(db_path: Optional[str] = None):
    """Context manager for SQLite connections — auto-closes on exit."""
    conn = _get_connection(db_path)
    try:
        yield conn
    finally:
        conn.close()


def _ensure_tables(conn: sqlite3.Connection) -> None:
    """Create tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS notices (
            ref_no TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            agency TEXT NOT NULL,
            notice_type TEXT DEFAULT '',
            category TEXT DEFAULT '',
            area_of_delivery TEXT DEFAULT '',
            posted_date TEXT DEFAULT '',
            closing_date TEXT DEFAULT '',
            approved_budget REAL DEFAULT 0,
            description TEXT DEFAULT '',
            url TEXT DEFAULT '',
            documents TEXT DEFAULT '[]',
            scraped_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS awards (
            ref_no TEXT NOT NULL,
            project_title TEXT NOT NULL,
            agency TEXT NOT NULL,
            supplier TEXT NOT NULL,
            award_amount REAL DEFAULT 0,
            award_date TEXT DEFAULT '',
            approved_budget REAL DEFAULT 0,
            bid_type TEXT DEFAULT '',
            url TEXT DEFAULT '',
            scraped_at TEXT NOT NULL,
            PRIMARY KEY (ref_no, supplier)
        );

        CREATE INDEX IF NOT EXISTS idx_notices_agency ON notices(agency);
        CREATE INDEX IF NOT EXISTS idx_notices_posted ON notices(posted_date);
        CREATE INDEX IF NOT EXISTS idx_awards_agency ON awards(agency);
        CREATE INDEX IF NOT EXISTS idx_awards_supplier ON awards(supplier);
        CREATE INDEX IF NOT EXISTS idx_awards_date ON awards(award_date);
    """)
    conn.commit()


# ── Notice CRUD ──

def upsert_notice(conn: sqlite3.Connection, notice: dict) -> None:
    """Insert or update a procurement notice."""
    conn.execute("""
        INSERT INTO notices (ref_no, title, agency, notice_type, category,
            area_of_delivery, posted_date, closing_date, approved_budget,
            description, url, documents, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ref_no) DO UPDATE SET
            title=excluded.title, agency=excluded.agency,
            notice_type=excluded.notice_type, category=excluded.category,
            area_of_delivery=excluded.area_of_delivery,
            posted_date=excluded.posted_date, closing_date=excluded.closing_date,
            approved_budget=excluded.approved_budget,
            description=excluded.description, url=excluded.url,
            documents=excluded.documents, scraped_at=excluded.scraped_at
    """, (
        notice["ref_no"], notice["title"], notice["agency"],
        notice.get("notice_type", ""), notice.get("category", ""),
        notice.get("area_of_delivery", ""), notice.get("posted_date", ""),
        notice.get("closing_date", ""), notice.get("approved_budget", 0),
        notice.get("description", ""), notice.get("url", ""),
        json.dumps(notice.get("documents", [])),
        datetime.now().isoformat(),
    ))
    conn.commit()


def search_notices(
    conn: sqlite3.Connection,
    query: str = "",
    agency: str = "",
    limit: int = 50,
) -> list[dict]:
    """Search cached notices by keyword and/or agency."""
    sql = "SELECT * FROM notices WHERE 1=1"
    params: list = []

    if query:
        sql += " AND (ref_no LIKE ? OR title LIKE ? OR description LIKE ? OR category LIKE ?)"
        q = f"%{query}%"
        params.extend([q, q, q, q])
    if agency:
        sql += " AND agency LIKE ?"
        params.append(f"%{agency}%")

    sql += " ORDER BY posted_date DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    results = []
    for row in rows:
        d = dict(row)
        try:
            d["documents"] = json.loads(d["documents"])
        except (json.JSONDecodeError, TypeError):
            d["documents"] = []
        results.append(d)
    return results


# ── Award CRUD ──

def _stable_award_ref(award: dict) -> str:
    """Return a stable ref_no for awards even when PhilGEPS does not expose refID."""
    ref_no = str(award.get("ref_no", "")).strip()
    if ref_no:
        return ref_no

    fingerprint = "|".join([
        str(award.get("project_title", "")).strip().lower(),
        str(award.get("agency", "")).strip().lower(),
        str(award.get("supplier", "")).strip().lower(),
        str(award.get("award_date", "")).strip(),
        str(award.get("award_amount", 0)),
    ])
    digest = hashlib.sha1(fingerprint.encode("utf-8")).hexdigest()[:16]
    return f"NOREF-{digest}"


def upsert_award(conn: sqlite3.Connection, award: dict) -> None:
    """Insert or update an award record."""
    ref_no = _stable_award_ref(award)
    project_title = str(award.get("project_title", "")).strip() or "(Untitled Project)"
    agency = str(award.get("agency", "")).strip() or "UNKNOWN"
    supplier = str(award.get("supplier", "")).strip() or "UNKNOWN SUPPLIER"

    conn.execute("""
        INSERT INTO awards (ref_no, project_title, agency, supplier,
            award_amount, award_date, approved_budget, bid_type, url, scraped_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ref_no, supplier) DO UPDATE SET
            project_title=excluded.project_title, agency=excluded.agency,
            award_amount=excluded.award_amount, award_date=excluded.award_date,
            approved_budget=excluded.approved_budget, bid_type=excluded.bid_type,
            url=excluded.url, scraped_at=excluded.scraped_at
    """, (
        ref_no, project_title, agency,
        supplier, award.get("award_amount", 0),
        award.get("award_date", ""), award.get("approved_budget", 0),
        award.get("bid_type", ""), award.get("url", ""),
        datetime.now().isoformat(),
    ))
    conn.commit()


def search_awards(
    conn: sqlite3.Connection,
    agency: str = "",
    supplier: str = "",
    limit: int = 50,
) -> list[dict]:
    """Search cached awards by agency and/or supplier."""
    sql = "SELECT * FROM awards WHERE 1=1"
    params: list = []

    if agency:
        sql += " AND agency LIKE ?"
        params.append(f"%{agency}%")
    if supplier:
        sql += " AND supplier LIKE ?"
        params.append(f"%{supplier}%")

    sql += " ORDER BY award_date DESC LIMIT ?"
    params.append(limit)

    return [dict(row) for row in conn.execute(sql, params).fetchall()]


# ── Analytics ──

def get_supplier_stats(conn: sqlite3.Connection, supplier: str) -> dict:
    """Get aggregate stats for a supplier."""
    row = conn.execute("""
        SELECT COUNT(*) as total_awards, SUM(award_amount) as total_value,
               COUNT(DISTINCT agency) as agency_count
        FROM awards WHERE supplier LIKE ?
    """, (f"%{supplier}%",)).fetchone()

    agencies = conn.execute("""
        SELECT DISTINCT agency FROM awards WHERE supplier LIKE ?
    """, (f"%{supplier}%",)).fetchall()

    return {
        "total_awards": row["total_awards"] if row else 0,
        "total_value": row["total_value"] or 0,
        "agency_count": row["agency_count"] if row else 0,
        "agencies": [r["agency"] for r in agencies],
    }


def get_agency_stats(conn: sqlite3.Connection, agency: str) -> dict:
    """Get aggregate stats for a procuring entity."""
    row = conn.execute("""
        SELECT COUNT(*) as total_awards, SUM(award_amount) as total_spending
        FROM awards WHERE agency LIKE ?
    """, (f"%{agency}%",)).fetchone()

    top_suppliers = conn.execute("""
        SELECT supplier, COUNT(*) as cnt, SUM(award_amount) as total
        FROM awards WHERE agency LIKE ?
        GROUP BY supplier ORDER BY total DESC LIMIT 10
    """, (f"%{agency}%",)).fetchall()

    return {
        "total_awards": row["total_awards"] if row else 0,
        "total_spending": row["total_spending"] or 0,
        "top_suppliers": [dict(r) for r in top_suppliers],
    }

