import sqlite3
import unittest

from probid_probing_agent.core.analysis.detectors import analyze_probe_findings


def _build_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(
        """
        CREATE TABLE notices (
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

        CREATE TABLE awards (
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
        """
    )

    # Enough notices for non-constrained data quality and mode profiling
    notices = [
        (
            f"N{i}",
            f"Laptop procurement batch {i}",
            "DICT",
            "Public Bidding",
            "IT Equipment",
            "NCR",
            "2026-01-01",
            "2026-01-10",
            1_000_000,
            "",
            "",
            "[]",
            "2026-01-01T00:00:00",
        )
        for i in range(1, 12)
    ]
    conn.executemany(
        """
        INSERT INTO notices (
            ref_no, title, agency, notice_type, category, area_of_delivery,
            posted_date, closing_date, approved_budget, description, url,
            documents, scraped_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        notices,
    )

    # Supplier with 3 awards => R1 medium confidence
    awards = [
        (
            f"A{i}",
            f"Laptop supply lot {i}",
            "DICT",
            "ACME CORP",
            990_000,
            f"2026-01-0{i}",
            1_000_000,
            "",
            "",
            "2026-01-01T00:00:00",
        )
        for i in range(1, 4)
    ]
    conn.executemany(
        """
        INSERT INTO awards (
            ref_no, project_title, agency, supplier, award_amount, award_date,
            approved_budget, bid_type, url, scraped_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        awards,
    )

    conn.commit()
    return conn


class ProbeOutputContractTests(unittest.TestCase):
    def test_probe_output_has_contract_keys(self):
        conn = _build_conn()
        result = analyze_probe_findings(conn, query="laptop", pages_scanned=1)

        self.assertIn("metadata", result)
        self.assertIn("summary", result)
        self.assertIn("risk_map", result)
        self.assertIn("findings", result)

        self.assertIn("data_quality_status", result["summary"])
        self.assertIn("data_quality_note", result["summary"])

        if result["findings"]:
            finding = result["findings"][0]
            self.assertIn("reason_code", finding)
            self.assertIn("confidence", finding)
            self.assertIn("refs", finding)
            self.assertIn("follow_up", finding)

    def test_probe_respects_min_confidence_filter(self):
        conn = _build_conn()
        all_result = analyze_probe_findings(conn, query="laptop", min_confidence="low")
        high_result = analyze_probe_findings(conn, query="laptop", min_confidence="high")

        self.assertGreaterEqual(len(all_result["findings"]), len(high_result["findings"]))
        self.assertEqual(high_result["metadata"]["min_confidence"], "high")

        for finding in high_result["findings"]:
            self.assertEqual(finding["confidence"], "high")

    def test_probe_respects_max_findings(self):
        conn = _build_conn()
        result = analyze_probe_findings(conn, query="laptop", max_findings=1)

        self.assertEqual(result["metadata"]["max_findings"], 1)
        self.assertLessEqual(len(result["findings"]), 1)
        self.assertEqual(result["summary"]["finding_count"], len(result["findings"]))


if __name__ == "__main__":
    unittest.main()
